from __future__ import annotations

import importlib.util
import os
import platform
import sys
from typing import Any

from app.database.connection import (
    DatabaseConfigError,
    check_database_connection,
    get_database_settings,
)


class ReadinessService:
    """
    Checks whether the local BTQ environment is ready to run project workflows.
    """

    REQUIRED_PACKAGES = {
        "requests": "requests",
        "psycopg": "psycopg",
        "dotenv": "python-dotenv",
    }

    def _mask_database_url(self, database_url: str) -> str:
        if "://" not in database_url or "@" not in database_url:
            return database_url
        scheme, rest = database_url.split("://", 1)
        if ":" not in rest.split("@", 1)[0]:
            return f"{scheme}://***@{rest.split('@', 1)[1]}"
        _, host_part = rest.split("@", 1)
        return f"{scheme}://***:***@{host_part}"

    def _check_python(self) -> dict[str, Any]:
        version_info = sys.version_info
        is_supported = version_info >= (3, 12)
        return {
            "status": "ok" if is_supported else "error",
            "version": platform.python_version(),
            "executable": sys.executable,
            "requires": ">=3.12",
        }

    def _check_packages(self) -> dict[str, Any]:
        packages = {}
        missing = []
        for import_name, package_name in self.REQUIRED_PACKAGES.items():
            installed = importlib.util.find_spec(import_name) is not None
            packages[package_name] = "ok" if installed else "missing"
            if not installed:
                missing.append(package_name)
        return {
            "status": "ok" if not missing else "error",
            "packages": packages,
            "missing": missing,
        }

    def _check_environment(self) -> dict[str, Any]:
        checks = {
            "DATABASE_TARGET": bool((os.getenv("DATABASE_TARGET") or "").strip()),
            "SEC_CONTACT_NAME": bool((os.getenv("SEC_CONTACT_NAME") or "").strip()),
            "SEC_CONTACT_EMAIL": bool((os.getenv("SEC_CONTACT_EMAIL") or "").strip()),
        }
        missing = sorted(name for name, present in checks.items() if not present)
        try:
            settings = get_database_settings()
            database_status = "ok"
            database_target = settings.database_target
            database_url = self._mask_database_url(settings.database_url)
        except DatabaseConfigError as exc:
            database_status = "error"
            database_target = os.getenv("DATABASE_TARGET") or "default"
            database_url = None
            missing.append("database_url")
            return {
                "status": "error",
                "database_status": database_status,
                "database_target": database_target,
                "database_url": database_url,
                "missing": sorted(set(missing)),
                "error": str(exc),
            }

        return {
            "status": "ok" if not missing else "warning",
            "database_status": database_status,
            "database_target": database_target,
            "database_url": database_url,
            "missing": sorted(set(missing)),
        }

    def _check_database(self, include_database: bool) -> dict[str, Any]:
        if not include_database:
            return {
                "status": "skipped",
                "reason": "database check disabled",
            }
        try:
            return check_database_connection()
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
            }

    def check_readiness(self, include_database: bool = True) -> dict[str, Any]:
        python_check = self._check_python()
        package_check = self._check_packages()
        environment_check = self._check_environment()
        database_check = self._check_database(include_database)
        section_statuses = [
            python_check["status"],
            package_check["status"],
            environment_check["status"],
            database_check["status"],
        ]
        if "error" in section_statuses:
            overall_status = "error"
        elif "warning" in section_statuses:
            overall_status = "warning"
        else:
            overall_status = "ok"

        return {
            "status": overall_status,
            "checks": {
                "python": python_check,
                "packages": package_check,
                "environment": environment_check,
                "database": database_check,
            },
        }
