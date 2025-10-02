from __future__ import annotations
import psycopg2
from contextlib import contextmanager
from typing import Iterator
from .config import settings


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
