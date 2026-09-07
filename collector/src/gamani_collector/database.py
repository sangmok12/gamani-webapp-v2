from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from gamani_collector.settings import get_settings


def create_database_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)
