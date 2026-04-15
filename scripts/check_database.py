from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import DatabaseConfigError, check_database_connection


def main() -> None:
    try:
        result = check_database_connection()
    except DatabaseConfigError as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
