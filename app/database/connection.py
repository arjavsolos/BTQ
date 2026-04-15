from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    database_url: str
    pool_enabled: bool
    pool_min_size: int
    pool_max_size: int
    connect_timeout: int
    application_name: str


_POOL: Any | None = None


def _import_postgres_driver() -> tuple[Any, str]:
    try:
        import psycopg  # type: ignore

        return psycopg, "psycopg"
    except ImportError:
        import psycopg2  # type: ignore

        return psycopg2, "psycopg2"


class DatabaseConfigError(RuntimeError):
    pass


def _get_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _build_database_url_from_parts() -> str | None:
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    sslmode = os.getenv("DB_SSLMODE")

    if not all([host, name, user, password]):
        return None

    auth = f"{quote_plus(user)}:{quote_plus(password)}"
    url = f"postgresql://{auth}@{host}:{port}/{name}"
    if sslmode:
        url = f"{url}?sslmode={quote_plus(sslmode)}"
    return url


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_url = _build_database_url_from_parts()
    if not database_url:
        raise DatabaseConfigError(
            "Database config is missing. Set DATABASE_URL or the DB_HOST/DB_NAME/DB_USER/DB_PASSWORD variables."
        )
    return database_url


def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings(
        database_url=get_database_url(),
        pool_enabled=_get_bool_env("DATABASE_POOL_ENABLED", True),
        pool_min_size=int(os.getenv("DATABASE_POOL_MIN_SIZE", "1")),
        pool_max_size=int(os.getenv("DATABASE_POOL_MAX_SIZE", "5")),
        connect_timeout=int(os.getenv("DATABASE_CONNECT_TIMEOUT", "15")),
        application_name=os.getenv("DATABASE_APPLICATION_NAME", "btq"),
    )


def _build_connect_kwargs(settings: DatabaseSettings) -> dict[str, Any]:
    return {
        "connect_timeout": settings.connect_timeout,
        "application_name": settings.application_name,
    }


def create_connection(autocommit: bool = False) -> Any:
    driver, driver_name = _import_postgres_driver()
    settings = get_database_settings()
    connection = driver.connect(settings.database_url, **_build_connect_kwargs(settings))

    if driver_name == "psycopg":
        connection.autocommit = autocommit
    else:
        connection.autocommit = autocommit

    return connection


def get_pool() -> Any:
    global _POOL
    if _POOL is not None:
        return _POOL

    settings = get_database_settings()
    if not settings.pool_enabled:
        return None

    try:
        from psycopg_pool import ConnectionPool  # type: ignore
    except ImportError:
        return None

    _POOL = ConnectionPool(
        conninfo=settings.database_url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        kwargs=_build_connect_kwargs(settings),
        open=True,
    )
    return _POOL


def close_pool() -> None:
    global _POOL
    if _POOL is not None:
        _POOL.close()
        _POOL = None


@contextmanager
def get_connection(autocommit: bool = False) -> Iterator[Any]:
    pool = get_pool()
    if pool is not None:
        with pool.connection() as connection:
            previous_autocommit = getattr(connection, "autocommit", False)
            connection.autocommit = autocommit
            try:
                yield connection
                if not autocommit:
                    connection.commit()
            except Exception:
                if not autocommit:
                    connection.rollback()
                raise
            finally:
                connection.autocommit = previous_autocommit
        return

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


def check_database_connection() -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select current_database(), current_user, now();")
            database_name, database_user, checked_at = cursor.fetchone()
    settings = get_database_settings()
    return {
        "status": "ok",
        "database_name": database_name,
        "database_user": database_user,
        "checked_at": str(checked_at),
        "pool_enabled": settings.pool_enabled,
        "pool_min_size": settings.pool_min_size,
        "pool_max_size": settings.pool_max_size,
        "application_name": settings.application_name,
    }
