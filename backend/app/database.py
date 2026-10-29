"""Conexão com o PostgreSQL (SQLAlchemy). A URL vem de DATABASE_URL."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency do FastAPI: uma sessão por requisição, sempre fechada no fim."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
