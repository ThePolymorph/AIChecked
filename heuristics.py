"""Fast, rule-based signals common in LLM-generated English prose.

These are weak, gameable tells — useful for a quick sanity check, not proof.
Complements the statistical Binoculars scorer in ``scoring.py``.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import List, Sequence


# ChatGPT-era words/phrases (curated, not exhaustive)
AI_BUZZWORDS = {
    "crucial", "delve", "delves", "delving", "tapestry", "landscape", "testament",
    "underscores", "underscore", "foster", "fosters", "fostering", "navigate",
    "navigates", "multifaceted", "robust", "comprehensive", "intricate",
    "pivotal", "seamless", "seamlessly", "ever-evolving", "game-changer",
    "holistic", "synergy", "leverage", "leveraging", "utilize", "utilizes",
    "realm", "embark", "embarks", "beacon", "bustling", "vibrant",
    "nuanced", "commendable", "noteworthy", "groundbreaking", "cutting-edge",
    "spearhead", "spearheaded", "myriad", "plethora", "interplay",
    "showcase", "showcases", "elevate", "elevates",
}

SIGNPOST_PHRASES = [
    r"\bit'?s important to note\b",
    r"\bit is worth noting\b",
    r"\bin today'?s (?:world|landscape|society|age)\b",
    r"\bin conclusion\b",
    r"\bto summarize\b",
    r"\bfurthermore\b",
    r"\bmoreover\b",
    r"\badditionally\b",
    r"\bthat said\b",
    r"\bon the other hand\b",
    r"\bas we (?:have )?seen\b",
    r"\blet'?s (?:dive|delve) (?:in|into)\b",
    r"\bplays a (?:crucial|vital|key|pivotal) role\b",
    r"\ba testament to\b",
    r"\bnot only .{3,40} but also\b",
    r"\bhere'?s (?:the thing|why|how)\b",
    r"\bthe bottom line\b",
]

# "fast, reliable, and scalable" / "clear, concise, and compelling"
RULE_OF_THREE = [
    re.compile(
        r"\b(?:\w+(?:ly|ed|ing|ful|less|ous|ive|able|ible)?,"
        r"\s+){2}\w+(?:ly|ed|ing|ful|less|ous|ive|able|ible)?\s+and\s+\w+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\w+,\s+\w+,\s+and\s+\w+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhether\s+\w[\w\s]{0,25},\s+\w[\w\s]{0,25},\s+or\s+\w+",
        re.IGNORECASE,
    ),
]


@dataclass
class HeuristicSignal:
    """One interpretable flag from the quick checker."""

    name: str
    count: int
    weight: float
    detail: str
    triggered: bool = False

    @property
    def points(self) -> float:
        return self.weight if self.triggered else 0.0


@dataclass
class QuickCheckResult:
    """Aggregated quick-check output."""

    text: str
    word_count: int
    ai_tell_score: float  # 0–100, higher = more AI-like surface tells
    verdict: str  # low / medium / high
    signals: List[HeuristicSignal] = field(default_factory=list)
    disclaimer: str = (
        "Heuristic signals only. Em dashes and rule-of-three appear in good human "
        "writing too. Use alongside judgment or the statistical scorer."
    )


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:'\w+)?\b", text))


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _count_em_dashes(text: str) -> int:
    unicode_dashes = text.count("\u2014") + text.count("\u2013")
    spaced_double = len(re.findall(r"(?<!\w)--(?!\w)", text))
    return unicode_dashes + spaced_double


def _count_matches(patterns: Sequence[re.Pattern[str]], text: str) -> int:
    total = 0
    for pat in patterns:
        total += len(pat.findall(text))
    return total


def _count_phrases(patterns: Sequence[str], text: str) -> int:
    total = 0
    lowered = text.lower()
    for pat in patterns:
        total += len(re.findall(pat, lowered))
    return total


def _buzzword_hits(text: str) -> tuple[int, List[str]]:
    words = re.findall(r"\b[a-z][a-z'-]*\b", text.lower())
    found = sorted({w for w in words if w in AI_BUZZWORDS})
    return len(found), found


def _sentence_length_uniformity(sentences: Sequence[str]) -> tuple[float, str]:
    """Low coefficient of variation → eerily uniform rhythm (common in LLM prose)."""
    lengths = [len(s.split()) for s in sentences if s.split()]
    if len(lengths) < 3:
        return 0.0, "too few sentences to measure rhythm"
    mean_len = statistics.mean(lengths)
    if mean_len == 0:
        return 0.0, "n/a"
    stdev = statistics.pstdev(lengths)
    cv = stdev / mean_len
    return cv, f"sentence length CV={cv:.2f} (low < 0.35 often feels machine-smooth)"


def quick_check(text: str) -> QuickCheckResult:
    """Run all lightweight heuristics and return a scored report."""
    text = text.strip()
    wc = _word_count(text)
    if wc == 0:
        return QuickCheckResult(
            text=text,
            word_count=0,
            ai_tell_score=0.0,
            verdict="low",
            signals=[],
        )

    signals: List[HeuristicSignal] = []

    em_count = _count_em_dashes(text)
    em_per_100 = (em_count / wc) * 100
    # ChatGPT often clusters em dashes; >1.5 per 100 words is a soft flag
    em_triggered = em_count >= 2 and em_per_100 >= 1.0
    signals.append(
        HeuristicSignal(
            name="em_dashes",
            count=em_count,
            weight=18.0,
            triggered=em_triggered,
            detail=f"{em_count} em/en dash(es) ({em_per_100:.1f} per 100 words)",
        )
    )

    triple_count = _count_matches(RULE_OF_THREE, text)
    triple_triggered = triple_count >= 2
    signals.append(
        HeuristicSignal(
            name="rule_of_three",
            count=triple_count,
            weight=15.0,
            triggered=triple_triggered,
            detail=f"{triple_count} rule-of-three list pattern(s) (e.g. 'X, Y, and Z')",
        )
    )

    buzz_n, buzz_words = _buzzword_hits(text)
    buzz_triggered = buzz_n >= 2
    buzz_detail = f"{buzz_n} AI-era buzzword(s)"
    if buzz_words:
        preview = ", ".join(buzz_words[:6])
        if len(buzz_words) > 6:
            preview += ", …"
        buzz_detail += f": {preview}"
    signals.append(
        HeuristicSignal(
            name="buzzwords",
            count=buzz_n,
            weight=12.0,
            triggered=buzz_triggered,
            detail=buzz_detail,
        )
    )

    signpost_n = _count_phrases(SIGNPOST_PHRASES, text)
    signpost_triggered = signpost_n >= 2
    signals.append(
        HeuristicSignal(
            name="signpost_phrases",
            count=signpost_n,
            weight=14.0,
            triggered=signpost_triggered,
            detail=f"{signpost_n} essay-like transition(s) (furthermore, in conclusion, …)",
        )
    )

    sentences = _sentences(text)
    cv, cv_detail = _sentence_length_uniformity(sentences)
    uniform_triggered = len(sentences) >= 4 and cv < 0.35
    signals.append(
        HeuristicSignal(
            name="uniform_sentences",
            count=len(sentences),
            weight=10.0,
            triggered=uniform_triggered,
            detail=cv_detail,
        )
    )

    # Numbered / bullet list blocks (LLM loves structured outlines)
    list_blocks = len(re.findall(r"(?:^|\n)\s*(?:\d+[.)]|[-*•])\s+\S", text))
    list_triggered = list_blocks >= 3
    signals.append(
        HeuristicSignal(
            name="list_heavy",
            count=list_blocks,
            weight=8.0,
            triggered=list_triggered,
            detail=f"{list_blocks} list item line(s)",
        )
    )

    # Opening with a broad contextual wind-up
    windup = bool(
        re.match(
            r"^(?:In (?:today's|the|an)|Throughout history|Since the dawn|"
            r"When it comes to|In recent years)",
            text,
            re.IGNORECASE,
        )
    )
    signals.append(
        HeuristicSignal(
            name="generic_opener",
            count=1 if windup else 0,
            weight=8.0,
            triggered=windup,
            detail="starts with a broad, essay-style opener" if windup else "no generic opener",
        )
    )

    colon_openers = len(re.findall(r"\b\w[\w\s]{0,20}:\s", text))
    colon_triggered = colon_openers >= 3
    signals.append(
        HeuristicSignal(
            name="colon_opener",
            count=colon_openers,
            weight=7.0,
            triggered=colon_triggered,
            detail=f"{colon_openers} clause(s) leading with a colon setup",
        )
    )

    rhetorical_q = len(re.findall(r"\?", text))
    rhet_triggered = rhetorical_q >= 2 and wc >= 80
    signals.append(
        HeuristicSignal(
            name="rhetorical_questions",
            count=rhetorical_q,
            weight=6.0,
            triggered=rhet_triggered,
            detail=f"{rhetorical_q} question mark(s) in text",
        )
    )

    max_points = sum(s.weight for s in signals)
    earned = sum(s.points for s in signals)
    score = min(100.0, (earned / max_points) * 100) if max_points else 0.0

    if score < 25:
        verdict = "low"
    elif score < 55:
        verdict = "medium"
    else:
        verdict = "high"

    return QuickCheckResult(
        text=text,
        word_count=wc,
        ai_tell_score=round(score, 1),
        verdict=verdict,
        signals=signals,
    )


def format_report(result: QuickCheckResult) -> str:
    """Human-readable terminal report."""
    lines = [
        "=== Quick heuristic check (instant, no models) ===",
        f"Words: {result.word_count}",
        f"AI-tell score: {result.ai_tell_score}/100 ({result.verdict} surface signals)",
        "",
        "Signals:",
    ]
    for s in result.signals:
        flag = "⚑" if s.triggered else "·"
        lines.append(f"  {flag} {s.name}: {s.detail}")
    lines.extend(
        [
            "",
            f"Verdict: {result.verdict} — "
            + {
                "low": "few typical LLM surface patterns",
                "medium": "some patterns worth a closer read",
                "high": "many typical LLM surface patterns (still not proof)",
            }[result.verdict],
            "",
            result.disclaimer,
        ]
    )
    return "\n".join(lines)
