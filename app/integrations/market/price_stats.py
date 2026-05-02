from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

import httpx


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    symbol: str
    label: str
    days: int
    rows: list[tuple[str, float]]
    source_url: str


_ASSET_PATTERNS: tuple[tuple[re.Pattern[str], tuple[str, str]], ...] = (
    (re.compile(r"(?i)\bgold\b|xau"), ("GC=F", "Gold futures (COMEX)")),
    (re.compile(r"(?i)\bsilver\b|xag"), ("SI=F", "Silver futures (COMEX)")),
    (re.compile(r"(?i)\boil\b|crude"), ("CL=F", "Crude oil futures (NYMEX)")),
    (re.compile(r"(?i)\bbitcoin\b|\bbtc\b"), ("BTC-USD", "Bitcoin (USD)")),
    (re.compile(r"(?i)\beth\b|ethereum"), ("ETH-USD", "Ethereum (USD)")),
    (re.compile(r"(?i)\bdse\b|dhaka stock|dsex"), ("^DSEX", "DSEX Index (Dhaka)")),
)


def _parse_days(query: str) -> int:
    m = re.search(r"(?i)\blast\s+(\d{1,4})\s*(day|days)\b", query)
    if m:
        return max(1, min(3650, int(m.group(1))))
    if re.search(r"(?i)\b(last|past)\s+month\b", query):
        return 30
    if re.search(r"(?i)\b(last|past)\s+week\b", query):
        return 7
    return 30


def detect_market_target(query: str) -> tuple[str, str] | None:
    for pat, target in _ASSET_PATTERNS:
        if pat.search(query):
            return target
    return None


async def fetch_market_snapshot_for_query(query: str) -> MarketSnapshot | None:
    target = detect_market_target(query)
    if not target:
        return None
    symbol, label = target
    days = _parse_days(query)
    end = int(datetime.now(tz=timezone.utc).timestamp())
    start = end - days * 86400
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}?period1={start}&period2={end}&interval=1d&events=history"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return None
        payload = r.json()
    except Exception:
        return None
    result = ((payload.get("chart") or {}).get("result") or [])
    if not result:
        return None
    item = result[0] or {}
    ts = item.get("timestamp") or []
    quote = ((item.get("indicators") or {}).get("quote") or [{}])[0] or {}
    closes = quote.get("close") or []
    rows: list[tuple[str, float]] = []
    for i, t in enumerate(ts):
        if i >= len(closes):
            break
        c = closes[i]
        if c is None:
            continue
        try:
            date_str = datetime.fromtimestamp(int(t), tz=timezone.utc).date().isoformat()
            rows.append((date_str, float(c)))
        except Exception:
            continue
    if not rows:
        return None
    return MarketSnapshot(symbol=symbol, label=label, days=days, rows=rows[-days:], source_url=url)


def market_snapshot_to_markdown(snapshot: MarketSnapshot) -> str:
    rows = snapshot.rows
    latest_date, latest_close = rows[-1]
    table = ["| Date | Close |", "|---|---:|"]
    for d, c in rows:
        table.append(f"| {d} | {c:.2f} |")
    return (
        f"{snapshot.label} — last {snapshot.days} day(s), symbol `{snapshot.symbol}`.\n\n"
        f"Latest close: **{latest_close:.2f}** on **{latest_date}**.\n\n"
        + "\n".join(table)
        + f"\n\nSource: {snapshot.source_url}"
    )
