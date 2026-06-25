"""Causal language model wrappers for log-probability extraction."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer


def detect_device() -> torch.device:
    """Pick the best available compute device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


class CausalLMScorer:
    """Wrapper around a Hugging Face causal LM for token-level scoring.

    Designed so observer/performer pairs can be swapped without touching
    scoring logic (e.g. gpt2 + gpt2-medium today, falcon-7b pairs later).
    """

    def __init__(
        self,
        model_name: str,
        device: Optional[torch.device] = None,
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name
        self.device = device or detect_device()
        self.max_length = max_length

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    def tokenize(self, text: str) -> torch.Tensor:
        """Tokenize text to input IDs on the scorer device."""
        encoded = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            add_special_tokens=True,
        )
        return encoded["input_ids"].to(self.device)

    @torch.no_grad()
    def get_logits(self, input_ids: torch.Tensor) -> torch.Tensor:
        """Return vocabulary logits for each next-token position.

        For input ``[x_0, ..., x_{L-1}]``, output shape is ``(L, vocab)`` where
        row ``i`` predicts token ``x_i`` from prefix ``x_{<i}``.
        """
        outputs = self.model(input_ids)
        return outputs.logits.squeeze(0)

    @torch.no_grad()
    def get_logprobs(self, text: str) -> Tuple[List[float], List[str]]:
        """Per-token log-probabilities of the observed tokens in *text*.

        Returns
        -------
        logprobs:
            One value per token (excluding the first BOS/prefix token which has
            no predicting context in the usual causal setup). Length is
            ``len(tokens) - 1``.
        tokens:
            String tokens aligned with ``logprobs`` (the predicted token at
            each step).
        """
        input_ids = self.tokenize(text)
        if input_ids.shape[1] < 2:
            return [], []

        logits = self.get_logits(input_ids)
        shift_logits = logits[:-1, :]
        shift_labels = input_ids.squeeze(0)[1:]

        log_probs = F.log_softmax(shift_logits, dim=-1)
        token_logprobs = log_probs.gather(
            1, shift_labels.unsqueeze(-1)
        ).squeeze(-1)

        token_ids = shift_labels.tolist()
        tokens = self.tokenizer.convert_ids_to_tokens(token_ids)
        return token_logprobs.cpu().tolist(), tokens

    @torch.no_grad()
    def get_token_distributions(
        self, text: str
    ) -> Tuple[torch.Tensor, torch.Tensor, List[str]]:
        """Return log-softmax distributions for cross-perplexity.

        Returns
        -------
        log_probs:
            ``(n_positions, vocab)`` log-softmax at each predicting position.
        input_ids:
            Full token ID tensor (for alignment checks across model pairs).
        tokens:
            Decoded tokens corresponding to predicted positions.
        """
        input_ids = self.tokenize(text)
        if input_ids.shape[1] < 2:
            empty = torch.empty(0, self.model.config.vocab_size, device=self.device)
            return empty, input_ids, []

        logits = self.get_logits(input_ids)
        shift_logits = logits[:-1, :]
        log_probs = F.log_softmax(shift_logits, dim=-1)

        shift_labels = input_ids.squeeze(0)[1:]
        tokens = self.tokenizer.convert_ids_to_tokens(shift_labels.tolist())
        return log_probs, input_ids, tokens

    @torch.no_grad()
    def get_logprobs_batch(
        self, texts: Sequence[str]
    ) -> List[Tuple[List[float], List[str]]]:
        """Score a batch of texts with padded forward passes."""
        if not texts:
            return []

        encoded = self.tokenizer(
            list(texts),
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding=True,
            add_special_tokens=True,
        )
        input_ids = encoded["input_ids"].to(self.device)
        attention_mask = encoded["attention_mask"].to(self.device)

        logits = self.model(input_ids, attention_mask=attention_mask).logits
        results: List[Tuple[List[float], List[str]]] = []

        for i in range(input_ids.shape[0]):
            ids = input_ids[i]
            mask = attention_mask[i]
            valid_len = int(mask.sum().item())
            if valid_len < 2:
                results.append(([], []))
                continue

            row_logits = logits[i, : valid_len - 1, :]
            shift_labels = ids[1:valid_len]
            log_probs = F.log_softmax(row_logits, dim=-1)
            token_logprobs = log_probs.gather(
                1, shift_labels.unsqueeze(-1)
            ).squeeze(-1)
            tokens = self.tokenizer.convert_ids_to_tokens(shift_labels.tolist())
            results.append((token_logprobs.cpu().tolist(), tokens))

        return results

    @torch.no_grad()
    def score_batch(
        self, texts: Sequence[str], batch_size: int = 4
    ) -> List[Tuple[List[float], List[str]]]:
        """Score multiple texts in padded mini-batches."""
        outputs: List[Tuple[List[float], List[str]]] = []
        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            outputs.extend(self.get_logprobs_batch(chunk))
        return outputs


class ModelPair:
    """Observer (smaller) + performer (larger) model pair sharing a tokenizer."""

    def __init__(
        self,
        observer_name: str = "gpt2",
        performer_name: str = "gpt2-medium",
        device: Optional[torch.device] = None,
        max_length: int = 512,
    ) -> None:
        self.device = device or detect_device()
        self.observer = CausalLMScorer(observer_name, self.device, max_length)
        self.performer = CausalLMScorer(performer_name, self.device, max_length)

        obs_vocab = self.observer.tokenizer.vocab_size
        perf_vocab = self.performer.tokenizer.vocab_size
        if obs_vocab != perf_vocab:
            raise ValueError(
                "Observer and performer must share a tokenizer/vocabulary "
                f"(got {obs_vocab} vs {perf_vocab})."
            )

    @property
    def shared_tokenizer(self):
        return self.observer.tokenizer
