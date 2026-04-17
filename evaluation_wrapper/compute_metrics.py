from __future__ import annotations

import argparse
from pathlib import Path

from .adapters import adapt_closed_loop_jsonl, adapt_interactionbench_micro_results
from .metrics import compute_report, save_report, write_normalized_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute the manuscript's Section 6 metrics from normalized or adapted logs.")
    parser.add_argument(
        "--input-format",
        choices=("interactionbench_micro", "closed_loop_jsonl"),
        required=True,
        help="Source log format to adapt before metric computation.",
    )
    parser.add_argument("--input-path", type=Path, required=True, help="Input result JSONL path.")
    parser.add_argument(
        "--scenario-path",
        type=Path,
        default=None,
        help="Scenario JSON path required by the interactionbench_micro adapter.",
    )
    parser.add_argument("--normalized-output", type=Path, required=True, help="Path for normalized event JSONL.")
    parser.add_argument("--report-output", type=Path, required=True, help="Path for the aggregate metric report JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.input_format == "interactionbench_micro":
        if args.scenario_path is None:
            raise SystemExit("--scenario-path is required for interactionbench_micro inputs.")
        episodes = adapt_interactionbench_micro_results(args.input_path, args.scenario_path)
    else:
        episodes = adapt_closed_loop_jsonl(args.input_path)

    write_normalized_jsonl(args.normalized_output, episodes)
    save_report(args.report_output, compute_report(episodes))


if __name__ == "__main__":
    main()
