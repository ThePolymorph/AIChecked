"""Statistical scoring functions for AI-text detection."""

from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn.functional as F

from models import CausalLMScorer, ModelPair


def _mean(values: list[float]) -> float:
    if not values:
        return float("nan")
    return sum(values) / len(values)


def log_perplexity(text: str, model: CausalLMScorer) -> float:
    """Average negative log-likelihood (log-PPL) of *text* under *model*.

    Statistical intuition
    ---------------------
    Log-perplexity measures how "surprised" the model is by each token in the
    text. Human writing tends to be less predictable to LMs (higher log-PPL)
    because humans sample from a broader, messier distribution than the narrow
    modes LLMs prefer. AI-generated text often sits in high-density regions of
    the model's probability landscape (low log-PPL).

    This is the classic perplexity baseline used since GPT-2 (Radford et al.,
    2019) and related to DetectGPT's curvature idea (Mitchell et al., 2023):
    both exploit that machine text occupies "flatter," more model-favored
    regions of the log-probability surface.

    Returns
    -------
    float
        ``-1/L * sum_i log p(x_i | x_{<i})``. Higher values suggest human text.
    """
    logprobs, _ = model.get_logprobs(text)
    if not logprobs:
        return float("nan")
    return -_mean(logprobs)


def perplexity(text: str, model: CausalLMScorer) -> float:
    """Standard perplexity ``exp(log-PPL)``.

    Lower perplexity means the model finds the text more predictable.
    """
    lp = log_perplexity(text, model)
    if math.isnan(lp):
        return float("nan")
    return math.exp(lp)


def log_cross_perplexity(
    text: str,
    observer: CausalLMScorer,
    performer: CausalLMScorer,
) -> float:
    """Log cross-perplexity between observer and performer (Binoculars xPPL).

    Implements Equation (3) from Hans et al. (2024):

        log X-PPL_{M1,M2}(s) = -1/L * sum_i  M1(s)_i · log M2(s)_i

    where ``·`` is the dot product over the vocabulary at each position.

    Statistical intuition
    ---------------------
    At each token position, we compare the *full* next-token distributions of
    two related models. When both models agree strongly (as they often do on
    machine text from a similar pretraining distribution), the cross-entropy is
    low. Human text tends to make the performer assign probability mass
    differently than the observer expects, raising cross-perplexity. This
    captures the "curvature" or alignment of the two models' probability
    landscapes on the same surface (related to DetectGPT's perturbation-based
    curvature, but computed directly from two frozen models).

    Returns
    -------
    float
        Mean per-token cross-entropy between observer and performer distributions.
    """
    obs_log_probs, _, _ = observer.get_token_distributions(text)
    perf_log_probs, _, _ = performer.get_token_distributions(text)

    if obs_log_probs.numel() == 0 or perf_log_probs.numel() == 0:
        return float("nan")

    n = min(obs_log_probs.shape[0], perf_log_probs.shape[0])
    obs_log_probs = obs_log_probs[:n]
    perf_log_probs = perf_log_probs[:n]

    obs_probs = obs_log_probs.exp()
    # Cross-entropy: -sum_v p_obs(v) * log p_perf(v)
    cross_entropy_per_token = -(obs_probs * perf_log_probs).sum(dim=-1)
    return cross_entropy_per_token.mean().item()


def binoculars_score(
    text: str,
    observer: CausalLMScorer,
    performer: CausalLMScorer,
) -> float:
    """Binoculars detection score (Hans et al., 2024, Equation 4).

        B = log PPL_{observer}(s) / log X-PPL_{observer, performer}(s)

    Statistical intuition
    ---------------------
    Raw perplexity fails on high-variance prompts (the "capybara problem"):
    unusual topics inflate perplexity for both human and machine text. Dividing
    log-perplexity by cross-perplexity normalizes against the baseline
    predictability that *any* LM would exhibit on the same string. Human text
    yields a higher ratio because the observer is more surprised by the actual
    tokens than it is by the performer's full distribution; machine text keeps
    both numerator and denominator low, but their ratio separates classes better
    than perplexity alone.

    Returns
    -------
    float
        Higher scores suggest human-written text; lower scores suggest AI text.
    """
    log_ppl = log_perplexity(text, observer)
    log_xppl = log_cross_perplexity(text, observer, performer)

    if math.isnan(log_ppl) or math.isnan(log_xppl) or log_xppl == 0:
        return float("nan")
    return log_ppl / log_xppl


def cross_perplexity(
    text: str,
    observer_model: CausalLMScorer,
    performer_model: CausalLMScorer,
) -> float:
    """Exponentiated log cross-perplexity (for reporting alongside perplexity)."""
    lxp = log_cross_perplexity(text, observer_model, performer_model)
    if math.isnan(lxp):
        return float("nan")
    return math.exp(lxp)


def score_text(
    text: str,
    pair: ModelPair,
    method: str = "binoculars",
) -> Tuple[float, str]:
    """Return a detection score and method name for a single string."""
    if method == "binoculars":
        return binoculars_score(text, pair.observer, pair.performer), method
    if method == "perplexity":
        return log_perplexity(text, pair.observer), method
    raise ValueError(f"Unknown method: {method}")
