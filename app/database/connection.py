import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    database_target: str
    database_url: str
    pool_enabled: bool
    pool_min_size: int
    pool_max_size: int
    connect_timeout: int
    application_name: str


_POOL: Any | None = None
_DLL_PATH_INITIALIZED = False


def _initialize_windows_postgres_dll_path() -> None:
    global _DLL_PATH_INITIALIZED
    if _DLL_PATH_INITIALIZED or os.name != "nt":
        return

    candidate_dirs = []

    env_bin = os.getenv("POSTGRES_BIN_DIR")
    if env_bin:
        candidate_dirs.append(Path(env_bin))

    program_files = os.getenv("ProgramFiles")
    if program_files:
        postgres_root = Path(program_files) / "PostgreSQL"
        if postgres_root.exists():
            versions = sorted(
                [path for path in postgres_root.iterdir() if path.is_dir()],
                reverse=True,
            )
            for version_dir in versions:
                candidate_dirs.append(version_dir / "bin")

    for candidate in candidate_dirs:
        if not candidate.exists():
            continue
        try:
            os.add_dll_directory(str(candidate))
            current_path = os.environ.get("PATH", "")
            if str(candidate) not in current_path:
                os.environ["PATH"] = f"{candidate}{os.pathsep}{current_path}"
            _DLL_PATH_INITIALIZED = True
            return
        except (FileNotFoundError, OSError):
            continue


def _import_postgres_driver() -> tuple[Any, str]:
    _initialize_windows_postgres_dll_path()
    try:
        import psycopg  # type: ignore

        return psycopg, "psycopg"
    except ImportError:
        try:
            import psycopg2  # type: ignore

            return psycopg2, "psycopg2"
        except ImportError:
            import pg8000  # type: ignore

            return pg8000, "pg8000"


class DatabaseConfigError(RuntimeError):
    pass


def _get_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_database_target() -> str:
    return (os.getenv("DATABASE_TARGET") or "default").strip().lower()


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


def _get_target_database_url(database_target: str) -> str | None:
    if database_target in {"local", "localhost"}:
        return os.getenv("LOCAL_DATABASE_URL") or os.getenv("DATABASE_URL")
    if database_target in {"neon", "hosted", "demo"}:
        return os.getenv("NEON_DATABASE_URL") or os.getenv("HOSTED_DATABASE_URL") or os.getenv("DATABASE_URL")
    return os.getenv("DATABASE_URL")


def get_database_url() -> str:
    database_target = get_database_target()
    database_url = _get_target_database_url(database_target)
    if not database_url:
        database_url = _build_database_url_from_parts()
    if not database_url:
        raise DatabaseConfigError(
            "Database config is missing. Set DATABASE_URL, a target-specific URL such as "
            "LOCAL_DATABASE_URL or NEON_DATABASE_URL, or the DB_HOST/DB_NAME/DB_USER/DB_PASSWORD variables."
        )
    return database_url


def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings(
        database_target=get_database_target(),
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
    if driver_name == "pg8000":
        connection = driver.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "postgres"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            timeout=settings.connect_timeout,
        )
    else:
        connection = driver.connect(settings.database_url, **_build_connect_kwargs(settings))

    if driver_name == "psycopg":
        connection.autocommit = autocommit
    elif driver_name == "psycopg2":
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
        "database_target": settings.database_target,
        "database_name": database_name,
        "database_user": database_user,
        "checked_at": str(checked_at),
        "pool_enabled": settings.pool_enabled,
        "pool_min_size": settings.pool_min_size,
        "pool_max_size": settings.pool_max_size,
        "application_name": settings.application_name,
    }
