# Evaluation Methodology

The eval harness (`evals/`) runs the **real pipeline** over a fixed 15-prompt dataset and scores every generated report. It exists to answer two questions continuously:

1. *Is the research any good?* (quality metrics)
2. *Did the last change make it worse?* (regression gate)

## Metrics

| Metric | How it's measured |
|---|---|
| **Citation grounding** | Up to 8 substantive sentences are sampled across the report body; an LLM judge (temperature 0) classifies each as `supported` / `partial` / `unsupported` against the report's cited source snippets. Score = (supported + 0.5·partial) / judged. |
| **Coverage** | LLM judge scores 0–1 how completely the report answers the original prompt, and names missing aspects. |
| **Structure** | Deterministic, no LLM: intro ≥ 40 words, conclusion ≥ 30, a section per topic with ≥ 40 words each, ≥ 3 citations, sane total word count, comparative analysis present for multi-topic prompts. |
| **Ops** | From the tracker trace + real Groq `usage`: per-node latency, replan iterations, task fallback rate, tokens, **cost per report** (current Groq pricing constants in `run_evals.py`). |

## Dataset

`evals/dataset.jsonl` — 15 prompts across domains, mixing single-topic quick/medium/deep and multi-topic comparison prompts. Fixed on purpose: changes in scores mean changes in the system, not the workload.

## Running

```bash
make eval            # full dataset (needs GROQ_API_KEY + TAVILY_API_KEY)
python -m evals.run_evals --limit 3
make eval-baseline   # promote current results to evals/baseline.json
make eval-check      # exit 1 if grounding/coverage/structure drop >10% vs baseline
```

Each run writes `evals/results/<timestamp>.json` (per-prompt detail + aggregate) and prints a markdown summary table.

## Regression gate

`--compare` fails (exit 1) when any of `grounding_mean`, `coverage_mean`, `structure_mean` falls more than **10% relative** below `evals/baseline.json`. Wire `make eval-check` into CI as a nightly or pre-release job (it needs API keys, so it's not part of the default PR pipeline).

## Judge reliability notes

- Judges run at temperature 0 and return structured JSON; scores are clamped to [0, 1].
- Grounding judges against the **stored snippets**, not live pages — it measures whether the report says things its own sources support, which is the hallucination failure mode that matters here.
- Judge logic itself is unit-tested with mocked LLM responses (`tests/test_evals.py`).
