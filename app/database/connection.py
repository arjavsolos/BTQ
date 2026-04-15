from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator


def _import_postgres_driver() -> tuple[Any, str]:
    try:
        import psycopg  # type: ignore

        return psycopg, "psycopg"
    except ImportError:
        import psycopg2  # type: ignore

        return psycopg2, "psycopg2"


class DatabaseConfigError(RuntimeError):
    pass


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise DatabaseConfigError(
            "DATABASE_URL is not set. Add it to your environment or .env loader."
        )
    return database_url


def create_connection(autocommit: bool = False) -> Any:
    driver, driver_name = _import_postgres_driver()
    database_url = get_database_url()
    connection = driver.connect(database_url)

    if driver_name == "psycopg":
        connection.autocommit = autocommit
    else:
        connection.autocommit = autocommit

    return connection


@contextmanager
def get_connection(autocommit: bool = False) -> Iterator[Any]:
    connection = create_connection(autocommit=autocommit)
    try:
        yield connection
        if not autocommit:
            connection.commit()
    except Exception:
        if not autocommit:
            connection.rollback()
        raise
    finally:
        connection.close()
