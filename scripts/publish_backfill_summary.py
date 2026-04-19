from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    output_path = Path(os.getenv("BACKFILL_OUTPUT_PATH", "logs/backfill_output.json"))
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path or not output_path.exists():
        return

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    summary_lines = [
        "",
        "### Backfill Result",
        "",
        f"- Status: `{payload.get('status', 'unknown')}`",
        f"- Fetched records: `{payload.get('fetched_records', 'unknown')}`",
        f"- Upserted records: `{payload.get('upserted_records', 'unknown')}`",
    ]
    if payload.get("error"):
        summary_lines.append(f"- Error: `{payload['error']}`")

    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(summary_lines) + "\n")


if __name__ == "__main__":
    main()
