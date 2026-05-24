from __future__ import annotations

from typing import Any

from app.api.routes import analyze_trial_route


def create_app() -> dict[str, Any]:
    return {
        "name": "btq-api",
        "routes": {
            "analyze_trial": analyze_trial_route,
        },
    }
