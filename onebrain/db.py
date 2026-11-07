import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_URL = f"sqlite:///{DATA_DIR / 'onebrain.db'}"


def make_engine(url: str | None = None):
    url = url or os.environ.get("ONEBRAIN_DB_URL", DEFAULT_URL)
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args={"check_same_thread": False})


def init_db(engine) -> None:
    from . import models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(engine)


def session_for(engine) -> Session:
    return Session(engine)
