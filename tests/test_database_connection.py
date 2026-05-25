from __future__ import annotations

import unittest
from unittest.mock import patch

from app.database.connection import (
    create_connection_for_url,
    get_database_settings,
    get_database_target,
    get_database_url,
)


class DatabaseConnectionTests(unittest.TestCase):
    def test_get_database_target_defaults_to_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(get_database_target(), "default")

    def test_get_database_url_uses_local_database_url_for_local_target(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DATABASE_TARGET": "local",
                "LOCAL_DATABASE_URL": "postgresql://postgres:password@localhost:5432/btq_local",
                "DATABASE_URL": "postgresql://postgres:password@localhost:5432/btq_default",
            },
            clear=True,
        ):
            self.assertEqual(
                get_database_url(),
                "postgresql://postgres:password@localhost:5432/btq_local",
            )

    def test_get_database_url_uses_neon_database_url_for_hosted_target(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DATABASE_TARGET": "neon",
                "NEON_DATABASE_URL": (
                    "postgresql://user:password@ep-example.us-east-2.aws.neon.tech/neondb?sslmode=require"
                ),
            },
            clear=True,
        ):
            self.assertEqual(
                get_database_url(),
                "postgresql://user:password@ep-example.us-east-2.aws.neon.tech/neondb?sslmode=require",
            )

    def test_get_database_url_falls_back_to_db_parts(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DB_HOST": "localhost",
                "DB_PORT": "5432",
                "DB_NAME": "btq",
                "DB_USER": "postgres",
                "DB_PASSWORD": "password",
            },
            clear=True,
        ):
            self.assertEqual(
                get_database_url(),
                "postgresql://postgres:password@localhost:5432/btq",
            )

    def test_get_database_settings_exposes_selected_target(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DATABASE_TARGET": "local",
                "LOCAL_DATABASE_URL": "postgresql://postgres:password@localhost:5432/btq_local",
            },
            clear=True,
        ):
            settings = get_database_settings()

        self.assertEqual(settings.database_target, "local")
        self.assertEqual(settings.database_url, "postgresql://postgres:password@localhost:5432/btq_local")

    def test_create_connection_for_url_uses_explicit_database_url(self) -> None:
        class DriverStub:
            def __init__(self) -> None:
                self.calls: list[dict] = []

            def connect(self, database_url: str, **kwargs):
                self.calls.append({"database_url": database_url, "kwargs": kwargs})

                class ConnectionStub:
                    autocommit = False

                return ConnectionStub()

        driver = DriverStub()

        with patch("app.database.connection._import_postgres_driver", return_value=(driver, "psycopg")):
            connection = create_connection_for_url(
                "postgresql://postgres:password@localhost:5432/btq",
                autocommit=True,
                connect_timeout=3,
                application_name="btq-test",
            )

        self.assertTrue(connection.autocommit)
        self.assertEqual(
            driver.calls[0],
            {
                "database_url": "postgresql://postgres:password@localhost:5432/btq",
                "kwargs": {"connect_timeout": 3, "application_name": "btq-test"},
            },
        )


if __name__ == "__main__":
    unittest.main()
