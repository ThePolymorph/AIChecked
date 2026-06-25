"""Benchmark evaluation for perplexity vs Binoculars detection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score

from dataset import TextSample, build_evaluation_sets, load_dataset_samples
from models import ModelPair
from scoring import binoculars_score, log_perplexity


@dataclass
class MethodResult:
    """Metrics for one scoring method on one evaluation condition."""

    method: str
    condition: str
    auroc: float
    accuracy: float
    threshold: float
    false_positive_rate: float
    n_samples: int


def _finite_scores(
    samples: Sequence[TextSample],
    scores: Sequence[float],
) -> Tuple[np.ndarray, np.ndarray]:
    """Filter NaN scores; return labels and scores arrays."""
    labels: List[int] = []
    valid_scores: List[float] = []
    for sample, score in zip(samples, scores):
        if score is None or (isinstance(score, float) and math.isnan(score)):
            continue
        labels.append(sample.label)
        valid_scores.append(float(score))
    return np.array(labels), np.array(valid_scores)


def _threshold_at_median_human(
    labels: np.ndarray,
    scores: np.ndarray,
) -> float:
    """Pick threshold at the median score of human (label=1) samples."""
    human_scores = scores[labels == 1]
    if len(human_scores) == 0:
        return float(np.median(scores))
    return float(np.median(human_scores))


def _predict(labels: np.ndarray, scores: np.ndarray, threshold: float) -> np.ndarray:
    """Predict human (1) when score >= threshold, else AI (0)."""
    return (scores >= threshold).astype(int)


def evaluate_method(
    samples: Sequence[TextSample],
    scores: Sequence[float],
    method: str,
    condition: str,
    threshold: Optional[float] = None,
) -> MethodResult:
    """Compute AUROC, accuracy, and FPR for higher-score = human."""
    labels, valid_scores = _finite_scores(samples, scores)
    if len(labels) < 2 or len(np.unique(labels)) < 2:
        return MethodResult(
            method=method,
            condition=condition,
            auroc=float("nan"),
            accuracy=float("nan"),
            threshold=float("nan"),
            false_positive_rate=float("nan"),
            n_samples=len(labels),
        )

    auroc = float(roc_auc_score(labels, valid_scores))
    thr = threshold if threshold is not None else _threshold_at_median_human(labels, valid_scores)
    preds = _predict(labels, valid_scores, thr)

    human_mask = labels == 1
    fp = int(np.sum((preds == 0) & human_mask))
    fn = int(np.sum((preds == 1) & ~human_mask))
    tn = int(np.sum((preds == 0) & ~human_mask))
    tp = int(np.sum((preds == 1) & human_mask))

    fpr = fp / max(1, fp + tn)
    accuracy = float(accuracy_score(labels, preds))

    return MethodResult(
        method=method,
        condition=condition,
        auroc=auroc,
        accuracy=accuracy,
        threshold=thr,
        false_positive_rate=fpr,
        n_samples=len(labels),
    )


def score_samples(
    samples: Sequence[TextSample],
    pair: ModelPair,
) -> Dict[str, List[float]]:
    """Compute perplexity-baseline and Binoculars scores for all samples."""
    ppl_scores: List[float] = []
    bin_scores: List[float] = []

    for i, sample in enumerate(samples):
        print(f"  Scoring {i + 1}/{len(samples)} ({sample.attack})...", end="\r")
        ppl_scores.append(log_perplexity(sample.text, pair.observer))
        bin_scores.append(binoculars_score(sample.text, pair.observer, pair.performer))
    print()

    return {"perplexity": ppl_scores, "binoculars": bin_scores}


def run_evaluation(
    max_per_class: int = 40,
    output_path: str | Path = "results.csv",
    observer: str = "gpt2",
    performer: str = "gpt2-medium",
) -> pd.DataFrame:
    """Run full benchmark and save comparison table."""
    print("Loading dataset...")
    samples = load_dataset_samples(max_per_class=max_per_class)
    clean, attacked = build_evaluation_sets(samples)

    print(f"Loaded {len(samples)} samples ({sum(s.label for s in samples)} human, "
          f"{len(samples) - sum(s.label for s in samples)} AI).")
    print(f"Loading models: observer={observer}, performer={performer}...")
    pair = ModelPair(observer_name=observer, performer_name=performer)

    print("Scoring clean set...")
    clean_scores = score_samples(clean, pair)
    print("Scoring paraphrase-attacked set...")
    attacked_scores = score_samples(attacked, pair)

    # Shared threshold from clean human median (Binoculars)
    clean_labels, clean_bin = _finite_scores(clean, clean_scores["binoculars"])
    shared_thr_bin = _threshold_at_median_human(clean_labels, clean_bin)
    clean_labels_p, clean_ppl = _finite_scores(clean, clean_scores["perplexity"])
    shared_thr_ppl = _threshold_at_median_human(clean_labels_p, clean_ppl)

    results: List[MethodResult] = []
    for method, thr_key, thr in (
        ("perplexity", "perplexity", shared_thr_ppl),
        ("binoculars", "binoculars", shared_thr_bin),
    ):
        for condition, subset, score_list in (
            ("clean", clean, clean_scores[thr_key]),
            ("paraphrase_attack", attacked, attacked_scores[thr_key]),
        ):
            results.append(
                evaluate_method(subset, score_list, method, condition, threshold=thr)
            )

    rows = []
    detail_rows = []
    for sample, ppl, bino in zip(
        clean,
        clean_scores["perplexity"],
        clean_scores["binoculars"],
    ):
        detail_rows.append(
            {
                "condition": "clean",
                "label": sample.label,
                "source": sample.source,
                "perplexity_log_ppl": ppl,
                "binoculars": bino,
                "text_preview": sample.text[:120],
            }
        )
    for sample, ppl, bino in zip(
        attacked,
        attacked_scores["perplexity"],
        attacked_scores["binoculars"],
    ):
        detail_rows.append(
            {
                "condition": sample.attack if sample.label == 0 else "clean",
                "label": sample.label,
                "source": sample.source,
                "perplexity_log_ppl": ppl,
                "binoculars": bino,
                "text_preview": sample.text[:120],
            }
        )

    for r in results:
        rows.append(
            {
                "method": r.method,
                "condition": r.condition,
                "auroc": round(r.auroc, 4) if not math.isnan(r.auroc) else None,
                "accuracy": round(r.accuracy, 4) if not math.isnan(r.accuracy) else None,
                "threshold": round(r.threshold, 4) if not math.isnan(r.threshold) else None,
                "false_positive_rate": round(r.false_positive_rate, 4)
                if not math.isnan(r.false_positive_rate)
                else None,
                "n_samples": r.n_samples,
            }
        )

    summary = pd.DataFrame(rows)
    detail = pd.DataFrame(detail_rows)
    out = Path(output_path)
    summary.to_csv(out, index=False)
    detail.to_csv(out.with_name("results_detail.csv"), index=False)

    _print_comparison_table(summary, shared_thr_ppl, shared_thr_bin)
    print(f"\nResults saved to {out.resolve()}")
    return summary


def _print_comparison_table(
    summary: pd.DataFrame,
    thr_ppl: float,
    thr_bin: float,
) -> None:
    """Print a readable comparison of methods under clean vs attack."""
    print("\n" + "=" * 72)
    print("DETECTION BENCHMARK: Perplexity baseline vs Binoculars")
    print("=" * 72)
    print(f"Thresholds (median human on clean set): perplexity={thr_ppl:.4f}, binoculars={thr_bin:.4f}")
    print("Higher score => predicted human. AI label=0, Human label=1.\n")

    pivot_auroc = summary.pivot(index="method", columns="condition", values="auroc")
    pivot_acc = summary.pivot(index="method", columns="condition", values="accuracy")
    pivot_fpr = summary.pivot(index="method", columns="condition", values="false_positive_rate")

    print("AUROC (1.0 = perfect separation, 0.5 = random):")
    print(pivot_auroc.to_string())
    print("\nAccuracy at fixed threshold:")
    print(pivot_acc.to_string())
    print("\nFalse positive rate on human texts (lower is better):")
    print(pivot_fpr.to_string())

    print("\n--- Interpretation ---")
    if "paraphrase_attack" in pivot_auroc.columns and "clean" in pivot_auroc.columns:
        for method in pivot_auroc.index:
            clean_auc = pivot_auroc.loc[method, "clean"]
            attack_auc = pivot_auroc.loc[method, "paraphrase_attack"]
            if pd.notna(clean_auc) and pd.notna(attack_auc):
                delta = attack_auc - clean_auc
                direction = "holds up better" if delta > 0.02 else (
                    "degrades similarly" if abs(delta) <= 0.02 else "degrades more"
                )
                print(
                    f"  {method}: AUROC clean={clean_auc:.3f} -> attack={attack_auc:.3f} "
                    f"(delta {delta:+.3f}); {direction} under paraphrase attack."
                )
    print("=" * 72)


if __name__ == "__main__":
    run_evaluation()
