from __future__ import annotations
import psycopg2
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator
from .config import settings


@dataclass
class PgConfig:
    host: str
    port: int
    user: str
    password: str
    db: str


def _get_pg_conn():
    return psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    )


@contextmanager
def get_cursor() -> Iterator[psycopg2.extensions.cursor]:
    conn = _get_pg_conn()
    conn.autocommit = True
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()
        conn.close()


def upsert_symbol(cur, symbol: str) -> int:
    cur.execute(
        """
        INSERT INTO symbols(symbol)
        VALUES (%s)
        ON CONFLICT(symbol) DO UPDATE SET symbol=EXCLUDED.symbol
        RETURNING id
        """,
        (symbol,),
    )
    return cur.fetchone()[0]


def insert_candle(cur, symbol_id: int, ts, o, h, l, c, v):
    cur.execute(
        """
        INSERT INTO candles(time, symbol_id, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (time, symbol_id) DO UPDATE SET
          open = EXCLUDED.open,
          high = EXCLUDED.high,
          low = EXCLUDED.low,
          close = EXCLUDED.close,
          volume = EXCLUDED.volume
        """,
        (ts, symbol_id, o, h, l, c, v),
    )
