"""Dataset loading and paraphrase-attack utilities."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Sequence

import nltk
from nltk.corpus import wordnet

if TYPE_CHECKING:
    from models import CausalLMScorer


@dataclass
class TextSample:
    """A single labeled text example."""

    text: str
    label: int  # 0 = AI-generated, 1 = human-written
    source: str
    attack: str = "clean"  # "clean" or "paraphrase"


def _ensure_nltk_data() -> None:
    for resource in ("wordnet", "omw-1.4", "averaged_perceptron_tagger_eng"):
        try:
            nltk.data.find(
                "corpora/wordnet"
                if resource == "wordnet"
                else (
                    "corpora/omw-1.4"
                    if resource == "omw-1.4"
                    else "taggers/averaged_perceptron_tagger_eng"
                )
            )
        except LookupError:
            pkg = resource.replace("_eng", "")
            nltk.download(pkg, quiet=True)


def _get_synonyms(word: str, pos: Optional[str] = None) -> List[str]:
    """Return synonym lemmas for *word* using WordNet."""
    wn_pos = None
    if pos and pos.startswith("J"):
        wn_pos = wordnet.ADJ
    elif pos and pos.startswith("V"):
        wn_pos = wordnet.VERB
    elif pos and pos.startswith("R"):
        wn_pos = wordnet.ADV
    elif pos and pos.startswith("N"):
        wn_pos = wordnet.NOUN

    synsets = wordnet.synsets(word, pos=wn_pos) if wn_pos else wordnet.synsets(word)
    lemmas: List[str] = []
    for syn in synsets:
        for lemma in syn.lemmas():
            candidate = lemma.name().replace("_", " ")
            if candidate.lower() != word.lower():
                lemmas.append(candidate)
    return lemmas


def paraphrase_attack(
    text: str,
    replace_ratio: float = 0.15,
    seed: Optional[int] = None,
) -> str:
    """Lightweight paraphrase via random synonym substitution.

    Replaces a fraction of content words with WordNet synonyms. This simulates
    a naive evasion attack: surface form changes while semantics stay similar.

    Parameters
    ----------
    text:
        Input string to perturb.
    replace_ratio:
        Approximate fraction of eligible words to replace.
    seed:
        Optional RNG seed for reproducibility.
    """
    _ensure_nltk_data()
    rng = random.Random(seed)

    tokens = nltk.word_tokenize(text)
    tagged = nltk.pos_tag(tokens)

    eligible_indices = [
        i
        for i, (tok, pos) in enumerate(tagged)
        if re.match(r"^[A-Za-z]+$", tok) and pos.startswith(("N", "V", "J", "R"))
    ]
    if not eligible_indices:
        return text

    n_replace = max(1, int(len(eligible_indices) * replace_ratio))
    replace_indices = set(rng.sample(eligible_indices, min(n_replace, len(eligible_indices))))

    out_tokens: List[str] = []
    for i, (tok, pos) in enumerate(tagged):
        if i not in replace_indices:
            out_tokens.append(tok)
            continue
        syns = _get_synonyms(tok, pos)
        if syns:
            out_tokens.append(rng.choice(syns))
        else:
            out_tokens.append(tok)

    return nltk.tokenize.space_join(out_tokens)


def _load_hc3(max_per_class: int = 40) -> List[TextSample]:
    """Load human/ChatGPT pairs from Hello-SimpleAI/HC3 (English subset)."""
    from datasets import load_dataset

    subsets = ["open_qa", "wiki_csai", "medicine", "finance"]
    samples: List[TextSample] = []
    human_count = 0
    ai_count = 0

    for subset in subsets:
        if human_count >= max_per_class and ai_count >= max_per_class:
            break
        try:
            ds = load_dataset("Hello-SimpleAI/HC3", subset, split="train")
        except Exception:
            continue

        for row in ds:
            human_answers = row.get("human_answers") or []
            chatgpt_answers = row.get("chatgpt_answers") or []

            for ans in human_answers:
                if human_count >= max_per_class:
                    break
                text = str(ans).strip()
                if len(text.split()) < 50:
                    continue
                samples.append(TextSample(text=text, label=1, source=f"hc3/{subset}"))
                human_count += 1

            for ans in chatgpt_answers:
                if ai_count >= max_per_class:
                    break
                text = str(ans).strip()
                if len(text.split()) < 50:
                    continue
                samples.append(TextSample(text=text, label=0, source=f"hc3/{subset}"))
                ai_count += 1

    return samples


def _generate_gpt2_paragraph(prompt: str, scorer: CausalLMScorer) -> str:
    """Generate a short paragraph with a local GPT-2 model."""
    import torch

    input_ids = scorer.tokenize(prompt)
    with torch.no_grad():
        output_ids = scorer.model.generate(
            input_ids,
            max_new_tokens=120,
            do_sample=True,
            temperature=0.8,
            top_p=0.9,
            pad_token_id=scorer.tokenizer.eos_token_id,
        )
    full = scorer.tokenizer.decode(output_ids[0], skip_special_tokens=True)
    if full.startswith(prompt):
        return full[len(prompt) :].strip()
    return full.strip()


def _load_synthetic(max_per_class: int = 20) -> List[TextSample]:
    """Fallback: WikiText human snippets + GPT-2 generations."""
    from datasets import load_dataset

    from models import CausalLMScorer

    wiki = load_dataset("wikitext", "wikitext-2-raw-v1", split="train")
    samples: List[TextSample] = []
    human_count = 0

    for row in wiki:
        text = str(row["text"]).strip()
        if len(text.split()) < 80:
            continue
        samples.append(TextSample(text=text[:800], label=1, source="wikitext"))
        human_count += 1
        if human_count >= max_per_class:
            break

    scorer = CausalLMScorer("gpt2", max_length=256)
    prompts = [
        "The history of astronomy began when",
        "In modern biology, researchers have discovered that",
        "The economic impact of climate change includes",
        "Ancient civilizations developed agriculture by",
        "Computer science emerged as a discipline because",
    ]
    ai_count = 0
    while ai_count < max_per_class:
        prompt = prompts[ai_count % len(prompts)]
        generated = _generate_gpt2_paragraph(prompt, scorer)
        # Keep only the newly generated continuation when possible
        if generated.startswith(prompt):
            generated = generated[len(prompt) :].strip()
        if len(generated.split()) < 40:
            generated = generated or _generate_gpt2_paragraph(prompt, scorer)
        samples.append(TextSample(text=generated[:800], label=0, source="gpt2"))
        ai_count += 1

    return samples


def load_dataset_samples(
    max_per_class: int = 40,
    seed: int = 42,
) -> List[TextSample]:
    """Load human vs AI text; HC3 first, synthetic Wikipedia+GPT-2 fallback."""
    try:
        samples = _load_hc3(max_per_class=max_per_class)
        n_human = sum(1 for s in samples if s.label == 1)
        n_ai = len(samples) - n_human
        if n_human >= max_per_class // 2 and n_ai >= max_per_class // 2:
            rng = random.Random(seed)
            rng.shuffle(samples)
            return samples
    except Exception as exc:
        print(f"HC3 unavailable ({exc}); using synthetic fallback.")
        samples = []

    if not samples:
        samples = _load_synthetic(max_per_class=max_per_class)

    rng = random.Random(seed)
    rng.shuffle(samples)
    return samples


def build_evaluation_sets(
    samples: Sequence[TextSample],
    attack_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[List[TextSample], List[TextSample]]:
    """Return (clean_set, paraphrase_attacked_set).

    Paraphrase attacks are applied only to AI-labeled samples (label 0).
  Human samples are copied unchanged into both sets for FPR measurement.
    """
    clean: List[TextSample] = list(samples)
    attacked: List[TextSample] = []

    for i, sample in enumerate(samples):
        if sample.label == 0:
            attacked.append(
                TextSample(
                    text=paraphrase_attack(sample.text, replace_ratio=attack_ratio, seed=seed + i),
                    label=0,
                    source=sample.source,
                    attack="paraphrase",
                )
            )
        else:
            attacked.append(
                TextSample(
                    text=sample.text,
                    label=sample.label,
                    source=sample.source,
                    attack="clean",
                )
            )

    return clean, attacked
