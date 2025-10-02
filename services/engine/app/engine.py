from __future__ import annotations
from typing import Optional, Dict, Any
from . import indicators as ind
from .db import get_cursor


class StrategyContext:
    def __init__(self, strategy_id: int, symbol_id: int, symbol: str, definition: Dict[str, Any]):
        self.strategy_id = strategy_id
        self.symbol_id = symbol_id
        self.symbol = symbol
        self.definition = definition


def fetch_last_closes(cur, symbol_id: int, n: int) -> list[float]:
    cur.execute(
        """
        SELECT close FROM candles
        WHERE symbol_id = %s
        ORDER BY time DESC
        LIMIT %s
        """,
        (symbol_id, n),
    )
    rows = cur.fetchall()
    return [r[0] for r in rows][::-1]  # oldest-first


def maybe_emit_signal(cur, ctx: StrategyContext) -> Optional[dict]:
    # MVP supports type: price_above_sma
    rule_type = ctx.definition.get("type")
    if rule_type != "price_above_sma":
        return None
    period = int(ctx.definition.get("period", 20))
    closes = fetch_last_closes(cur, ctx.symbol_id, max(period, 30))
    if len(closes) < period:
        return None
    avg = ind.sma(closes, period)
    if avg is None:
        return None
    price = closes[-1]
    if price > avg:
        return {
            "type": ctx.definition.get("signal", "BUY"),
            "details": {"price": price, "sma": avg, "period": period},
        }
    return None
