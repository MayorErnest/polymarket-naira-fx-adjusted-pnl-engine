"""Polymarket public Data API (v2) client. Read-only, no auth.

Docs: https://docs.polymarket.com/trading/wallet-activity
"""

import re
import time

import requests

BASE_URL = "https://data-api.polymarket.com/v2"
PAGE_SIZE = 100
TIMEOUT = 15
MAX_RETRIES = 4
MAX_PAGES = 500  # 50,000 rows; a safety stop, reported if hit

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_FLOW_KINDS = {"DEPOSIT": "deposit", "WITHDRAWAL": "withdrawal"}


class PolymarketError(RuntimeError):
    """Polymarket couldn't be reached or returned something unexpected."""


def is_valid_address(address: str) -> bool:
    return bool(_ADDRESS_RE.match(address.strip()))


def _get(path: str, params: dict) -> dict:
    """GET with backoff on rate limits, server errors and network failures."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = PolymarketError(f"HTTP {resp.status_code} from {path}")
            else:
                resp.raise_for_status()
                return resp.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            last_error = e
        except requests.HTTPError as e:  # 4xx other than 429: retrying won't help
            raise PolymarketError(f"Polymarket rejected the request to {path}: {e}") from e
        time.sleep(2**attempt)
    raise PolymarketError(f"Polymarket kept failing for {path}: {last_error}")


def _seconds(ts) -> float:
    """Timestamps may be epoch seconds or milliseconds."""
    ts = float(ts or 0)
    return ts / 1000 if ts > 1e12 else ts


def fetch_activity(address: str) -> tuple[list[dict], bool]:
    """All activity rows for a wallet, including deposits and withdrawals.

    Returns (rows, complete). complete is False only if the safety page limit
    was hit, in which case the OLDEST rows are missing and the UI must say so.
    """
    rows: list[dict] = []
    seen: set[tuple] = set()
    cursor = None
    for _ in range(MAX_PAGES):
        params = {
            "user": address.strip(),
            "limit": PAGE_SIZE,
            # v2 hides deposits/withdrawals unless asked for explicitly.
            "exclude_deposits_withdrawals": "false",
        }
        if cursor:
            params["cursor"] = cursor
        page = _get("/activity", params)
        for r in page.get("data") or []:
            key = (r.get("transaction_hash"), r.get("type"), r.get("token_id"), r.get("timestamp"))
            if key not in seen:
                seen.add(key)
                rows.append(r)
        pagination = page.get("pagination") or {}
        cursor = pagination.get("next_cursor")
        if not pagination.get("has_more") or not cursor:
            return rows, True
    return rows, False


def fetch_value(address: str) -> float:
    """Marked USD value of the wallet's positions.

    May not include unspent cash; the UI should let the user check this
    against the balance shown on Polymarket.
    """
    data = _get("/value", {"user": address.strip()}).get("data") or {}
    return float(data.get("value") or 0)


def _usd(row: dict) -> float | None:
    """Dollar amount of a deposit/withdrawal row, or None if absent.

    Deliberately never falls back to `size`, which means shares on trade rows.
    """
    for key in ("usdc_size", "amount", "value"):
        if row.get(key) is not None:
            return float(row[key])
    return None


def extract_flows(activity: list[dict]) -> list[dict]:
    """Deposit/withdrawal rows from raw activity, oldest first.

    Returns dicts with timestamp (epoch seconds), kind ("deposit"/"withdrawal"),
    usd (None if the API didn't give an amount) and tx hash.
    """
    flows = [
        {
            "timestamp": _seconds(r.get("timestamp")),
            "kind": _FLOW_KINDS[r["type"]],
            "usd": _usd(r),
            "tx": r.get("transaction_hash", ""),
        }
        for r in activity
        if r.get("type") in _FLOW_KINDS
    ]
    return sorted(flows, key=lambda f: f["timestamp"])