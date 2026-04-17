# Interactive Robot Eval Wrapper

This repository releases the lightweight evaluation wrapper referenced by the survey paper "Interactive Robot Learning in the Foundation Model Era".

The package turns the paper's Section 6 reporting contract into executable metrics for:

- `S_rec` and `L_rec` for post-failure recovery
- `Succ_clar` and `T_clar` for clarification behavior
- `Prec_abort`, `Rec_abort`, `FAR`, and `UCR` for safe fallback or abort
- `eta_corr` and `barK_rec` for correction efficiency
- `Delta_hor(H)` for horizon-conditioned degradation

The release is deliberately lightweight. It does not assume one simulator, one robot stack, or one benchmark package. Instead, it exposes a normalized event schema plus small adapters for two artifact formats already used in the companion repository:

- `InteractionBench-Micro` synthetic scaffold outputs
- closed-loop JSONL traces from the shared synthetic or `pybullet` backends

## Quick start

Run against the included scaffold demo:

```bash
python -m evaluation_wrapper.compute_metrics \
  --input-format interactionbench_micro \
  --input-path examples/scaffold_seed_results.jsonl \
  --scenario-path examples/scaffold_scenarios.json \
  --normalized-output examples/scaffold_normalized_from_release.jsonl \
  --report-output examples/scaffold_report_from_release.json
```

In the companion project, the same entrypoint is used as follows:

```bash
python -m Experiment.core_code.evaluation_wrapper.compute_metrics \
  --input-format interactionbench_micro \
  --input-path Experiment/analysis/eval_wrapper_seed/interactionbench_micro_synthetic_results.jsonl \
  --scenario-path Experiment/analysis/eval_wrapper_seed/interactionbench_micro_scenarios.json \
  --normalized-output Experiment/analysis/evaluation_wrapper_demo/scaffold_normalized.jsonl \
  --report-output Experiment/analysis/evaluation_wrapper_demo/scaffold_report.json
```

## Repository contents

- `evaluation_wrapper/metrics.py`: normalized schema and metric aggregation
- `evaluation_wrapper/adapters.py`: adapters from existing repository artifacts
- `evaluation_wrapper/compute_metrics.py`: CLI entrypoint
- `examples/`: normalized demo outputs and sample reports

## Scope

This is a metric-and-event layer, not a full benchmark suite. Its role is to make the survey's proposed reporting standard directly executable and easy to attach to existing environments.
