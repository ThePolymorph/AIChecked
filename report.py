"""Unified report combining heuristic and statistical detection."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from heuristics import QuickCheckResult, quick_check

DEFAULT_BINOCULARS_THRESHOLD = 1.0
DEFAULT_LOG_PPL_THRESHOLD = 4.0


@dataclass
class DeepCheckResult:
    """Statistical Binoculars + perplexity baseline."""

    binoculars: float
    log_perplexity: float
    binoculars_label: str
    perplexity_label: str
    ai_likelihood_pct: float
    models_ready: bool = True
    warning: Optional[str] = None


@dataclass
class CombinedReport:
    """Full scan result for API and web UI."""

    word_count: int
    surface_score: float
    surface_verdict: str
    ai_likelihood_pct: float
    human_likelihood_pct: float
    overall_verdict: str
    confidence: str
    signals: List[Dict[str, Any]]
    deep: Optional[DeepCheckResult] = None
    scan_mode: str = "quick"
    disclaimer: str = (
        "Scores are probabilistic signals, not proof. Short text (<100 words), "
        "edited prose, and non-native English can mislead both methods."
    )

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "word_count": self.word_count,
            "surface_score": self.surface_score,
            "surface_verdict": self.surface_verdict,
            "ai_likelihood_pct": self.ai_likelihood_pct,
            "human_likelihood_pct": self.human_likelihood_pct,
            "overall_verdict": self.overall_verdict,
            "confidence": self.confidence,
            "signals": self.signals,
            "scan_mode": self.scan_mode,
            "disclaimer": self.disclaimer,
        }
        if self.deep:
            data["deep"] = asdict(self.deep)
        return data


def _binoculars_to_ai_pct(binoculars: float) -> float:
    """Map Binoculars score to 0–100 AI-likelihood (higher B = more human)."""
    if math.isnan(binoculars):
        return 50.0
    # Centered at threshold 1.0; ~0.7 → high AI, ~1.3 → low AI
    ai_pct = 50.0 - (binoculars - DEFAULT_BINOCULARS_THRESHOLD) * 90.0
    return round(max(0.0, min(100.0, ai_pct)), 1)


def _overall_verdict(ai_pct: float) -> tuple[str, str]:
    if ai_pct < 30:
        return "likely_human", "low"
    if ai_pct < 55:
        return "uncertain", "medium"
    if ai_pct < 75:
        return "likely_ai", "medium"
    return "likely_ai", "high"


def _signal_dict(quick: QuickCheckResult) -> List[Dict[str, Any]]:
    labels = {
        "em_dashes": "Em dashes",
        "rule_of_three": "Rule of three",
        "buzzwords": "AI buzzwords",
        "signpost_phrases": "Signpost phrases",
        "uniform_sentences": "Uniform rhythm",
        "list_heavy": "List-heavy",
        "generic_opener": "Generic opener",
        "colon_opener": "Colon explanations",
        "rhetorical_questions": "Rhetorical questions",
    }
    return [
        {
            "id": s.name,
            "label": labels.get(s.name, s.name.replace("_", " ").title()),
            "triggered": s.triggered,
            "count": s.count,
            "detail": s.detail,
        }
        for s in quick.signals
    ]


def run_deep_check(text: str, pair: object) -> DeepCheckResult:
    """Run Binoculars statistical scoring."""
    from scoring import binoculars_score, log_perplexity

    warning = None
    wc = len(text.split())
    if wc < 100:
        warning = f"Only {wc} words — statistical scores are unreliable below ~100 words."

    bino = binoculars_score(text, pair.observer, pair.performer)
    ppl = log_perplexity(text, pair.observer)

    bino_label = "human" if bino >= DEFAULT_BINOCULARS_THRESHOLD else "ai"
    ppl_label = "human" if ppl >= DEFAULT_LOG_PPL_THRESHOLD else "ai"

    return DeepCheckResult(
        binoculars=round(bino, 4) if not math.isnan(bino) else float("nan"),
        log_perplexity=round(ppl, 4) if not math.isnan(ppl) else float("nan"),
        binoculars_label=bino_label,
        perplexity_label=ppl_label,
        ai_likelihood_pct=_binoculars_to_ai_pct(bino),
        warning=warning,
    )


def run_combined_scan(
    text: str,
    pair: Optional[object] = None,
    mode: str = "quick",
) -> CombinedReport:
    """Run quick, deep, or full scan and merge into one report.

    Parameters
    ----------
    mode:
        ``quick`` — heuristics only (instant).
        ``deep`` or ``full`` — heuristics + Binoculars (requires *pair*).
    """
    text = text.strip()
    quick = quick_check(text)
    deep: Optional[DeepCheckResult] = None

    if mode in ("deep", "full") and pair is not None:
        deep = run_deep_check(text, pair)

    if deep is not None:
        ai_pct = round(0.42 * quick.ai_tell_score + 0.58 * deep.ai_likelihood_pct, 1)
        scan_mode = "full"
    else:
        ai_pct = quick.ai_tell_score
        scan_mode = "quick"

    human_pct = round(100.0 - ai_pct, 1)
    verdict, confidence = _overall_verdict(ai_pct)

    return CombinedReport(
        word_count=quick.word_count,
        surface_score=quick.ai_tell_score,
        surface_verdict=quick.verdict,
        ai_likelihood_pct=ai_pct,
        human_likelihood_pct=human_pct,
        overall_verdict=verdict,
        confidence=confidence,
        signals=_signal_dict(quick),
        deep=deep,
        scan_mode=scan_mode,
    )
