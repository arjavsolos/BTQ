from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.readiness_service import ReadinessService


class ReadinessServiceTests(unittest.TestCase):
    def test_check_readiness_reports_ok_without_database(self) -> None:
        service = ReadinessService()

        with patch.dict(
            "os.environ",
            {
                "DATABASE_TARGET": "local",
                "LOCAL_DATABASE_URL": "postgresql://postgres:secret@localhost:5432/btq",
                "SEC_CONTACT_NAME": "BTQ Research",
                "SEC_CONTACT_EMAIL": "you@example.com",
            },
            clear=True,
        ):
            result = service.check_readiness(include_database=False)

        self.assertEqual(result["checks"]["database"]["status"], "skipped")
        self.assertEqual(result["checks"]["environment"]["status"], "ok")
        self.assertEqual(
            result["checks"]["environment"]["database_url"],
            "postgresql://***:***@localhost:5432/btq",
        )
        self.assertIn(result["status"], {"ok", "warning"})

    def test_check_readiness_reports_missing_environment_values(self) -> None:
        service = ReadinessService()

        with patch.dict(
            "os.environ",
            {
                "DATABASE_TARGET": "local",
                "LOCAL_DATABASE_URL": "postgresql://postgres:secret@localhost:5432/btq",
            },
            clear=True,
        ):
            result = service.check_readiness(include_database=False)

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["checks"]["environment"]["status"], "warning")
        self.assertEqual(
            result["checks"]["environment"]["missing"],
            ["SEC_CONTACT_EMAIL", "SEC_CONTACT_NAME"],
        )

    def test_check_readiness_surfaces_database_errors(self) -> None:
        service = ReadinessService()

        with (
            patch.dict(
                "os.environ",
                {
                    "DATABASE_TARGET": "local",
                    "LOCAL_DATABASE_URL": "postgresql://postgres:secret@localhost:5432/btq",
                    "SEC_CONTACT_NAME": "BTQ Research",
                    "SEC_CONTACT_EMAIL": "you@example.com",
                },
                clear=True,
            ),
            patch(
                "app.services.readiness_service.check_database_connection",
                side_effect=RuntimeError("database unavailable"),
            ),
        ):
            result = service.check_readiness(include_database=True)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["checks"]["database"]["status"], "error")
        self.assertEqual(result["checks"]["database"]["error"], "database unavailable")


if __name__ == "__main__":
    unittest.main()
