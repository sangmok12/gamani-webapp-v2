import psycopg

from gamani_collector.settings import get_settings


def check_connection(database_url: str) -> tuple[str, str]:
    """Return the connected database name and PostgreSQL version."""

    with psycopg.connect(database_url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), version()")
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("PostgreSQL connection check returned no result")

    database_name, version = row
    return str(database_name), str(version)


def main() -> None:
    settings = get_settings()
    database_name, version = check_connection(settings.database_url)
    print(f"Connected to database: {database_name}")
    print(version)


if __name__ == "__main__":
    main()

