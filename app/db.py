import sqlite3
from pathlib import Path
from . import config

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path=None):
    p = Path(path or config.DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA.read_text())
    return con
