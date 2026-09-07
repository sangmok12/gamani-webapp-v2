from gamani_collector.settings import Settings


def test_settings_accepts_explicit_database_url() -> None:
    settings = Settings(
        database_url="postgresql://user:password@localhost:5432/database",
        app_env="test",
    )

    assert settings.app_env == "test"
    assert settings.log_level == "INFO"

