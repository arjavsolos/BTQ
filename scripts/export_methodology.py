from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.research import build_methodology_snapshot, render_methodology_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the BTQ project methodology")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.format == "markdown":
        print(render_methodology_markdown())
        return
    print(json.dumps(build_methodology_snapshot(), indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
