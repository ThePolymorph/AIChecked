# AIChecked: Training-Free AI Text Detection

A small research project that detects machine-generated text using **local, open-source language models** — no API keys, no labeled training data, no fine-tuning.

The core idea follows [**Binoculars**](https://arxiv.org/abs/2401.12070) (Hans et al., ICML 2024): compare how two related causal LMs ("observer" and "performer") score the same text, and use the ratio of log-perplexity to cross-perplexity as a detection signal. This builds on the intuition behind [**DetectGPT**](https://arxiv.org/abs/2301.11305) (Mitchell et al., 2023) — machine text tends to occupy predictable, low-curvature regions of an LM's probability landscape — but implements a **pairwise, zero-shot** statistic instead of perturbation-based curvature.

## How it works

1. **Observer** (`gpt2`): smaller model that measures how surprising the text is.
2. **Performer** (`gpt2-medium`): larger model from the same family (shared tokenizer).
3. **Binoculars score**:
   ```
   B = log PPL_observer(text) / log X-PPL_observer,performer(text)
   ```
   - **log PPL**: average negative log-likelihood of the actual tokens under the observer.
   - **log X-PPL**: average cross-entropy between observer and performer next-token distributions at each position.

**Higher B → more likely human.** **Lower B → more likely AI.**

We also benchmark a **perplexity baseline** (log-PPL under the observer alone), which is simpler but more fragile to topic/prompt effects (the "capybara problem" in the Binoculars paper).

## Quick start

```bash
pip install -r requirements.txt
python -m nltk.downloader wordnet omw-1.4 punkt averaged_perceptron_tagger_eng
```

## AIChecked.com website

Full UI with instant **Quick scan** + optional **Deep scan** (Binoculars).

```powershell
pip install -r requirements.txt
python -m nltk.downloader wordnet omw-1.4 punkt averaged_perceptron_tagger_eng
uvicorn api:app --reload --port 8000
```

Open http://127.0.0.1:8000 — production deploy steps in [DEPLOY.md](DEPLOY.md).

### Quick heuristic scan (CLI)

Surface-pattern check for common LLM tells: em dashes, rule-of-three lists, buzzwords, signpost phrases, uniform sentence rhythm.

```bash
python main.py --quick --text "Paste text here."
python quick_app.py   # opens http://127.0.0.1:8765 in browser
```

**Honest caveat:** Good human writers use em dashes and parallel triplets too. Treat this as a fast red-flag pass, not evidence.

### Score a single text (statistical, slow)

```bash
python main.py --text "Your paragraph here."
```

### Run the full benchmark

```bash
python main.py --evaluate
```

Optional flags: `--max-per-class 40`, `--observer gpt2`, `--performer gpt2-medium`, `--output results.csv`.

## Project layout

| File | Purpose |
|------|---------|
| `models.py` | Load observer/performer LMs; `get_logprobs()`, device detection |
| `scoring.py` | `perplexity()`, `log_cross_perplexity()`, `binoculars_score()` |
| `dataset.py` | HC3 human/ChatGPT data + synonym paraphrase attacks |
| `evaluate.py` | AUROC / accuracy / FPR on clean vs attacked text |
| `main.py` | CLI entry point |
| `results.csv` | Summary metrics (written after `--evaluate`) |

## Evaluation design

- **Dataset**: [Hello-SimpleAI/HC3](https://huggingface.co/datasets/Hello-SimpleAI/HC3) (human vs ChatGPT answers). Falls back to WikiText-2 + GPT-2 generations if HC3 is unavailable.
- **Paraphrase attack**: WordNet synonym substitution on AI samples (~15% of content words) to simulate naive evasion.
- **Metrics**: AUROC, accuracy at a median-human threshold (fit on clean data), false positive rate on human texts.
- **Conditions**: (a) clean text, (b) AI samples paraphrased (humans unchanged).

## Swapping models

The scoring logic is model-agnostic. To try larger pairs later (e.g. Falcon-7B + Falcon-7B-Instruct), only change CLI flags or `ModelPair` defaults — observer and performer **must share a tokenizer**.

## Known limitations

- **Short text (<100 words)** produces unreliable scores; both perplexity and Binoculars need enough tokens for stable estimates.
- **Non-native English** can elevate false positives for perplexity-based methods (see Liang et al., 2023); treat scores as signals, not proof.
- **GPT-2 scoring ChatGPT text** is a domain mismatch — expect weaker absolute AUROC than the original paper's Falcon-7B setup.
- **Paraphrase attacks here are mild** (synonym swap). Stronger rewriting may reduce both methods.
- **No prompt access**: detectors see only the answer text, matching realistic deployment but making some edge cases harder.

## References

```bibtex
@inproceedings{hans2024binoculars,
  title={Spotting LLMs With Binoculars: Zero-Shot Detection of Machine-Generated Text},
  author={Hans, Abhimanyu and Schwarzschild, Avi and Cherepanova, Valeriia and Kazemi, Hamid and Saha, Aniruddha and Goldblum, Micah and Geiping, Jonas and Goldstein, Tom},
  booktitle={ICML},
  year={2024}
}

@inproceedings{mitchell2023detectgpt,
  title={DetectGPT: Zero-Shot Machine-Generated Text Detection using Probability Curvature},
  author={Mitchell, Eric and Lee, Yoonho and Khazatsky, Alexander and Manning, Christopher D and Finn, Chelsea},
  booktitle={ICML},
  year={2023}
}
```

## License

Research / educational use. Detection outputs should not be used as sole evidence in high-stakes settings without human review.
