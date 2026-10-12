"""Platform-independent naira profit maths. No Streamlit, no network."""

from dataclasses import dataclass

DEPOSIT = "deposit"
WITHDRAWAL = "withdrawal"


class FlowError(ValueError):
    """A row the maths can't use. The message says which row and why."""


@dataclass(frozen=True)
class Flow:
    """One deposit or withdrawal, with the naira the user actually paid or received."""

    kind: str  # "deposit" or "withdrawal" (any capitalisation)
    usd: float
    ngn: float | None  # None = the user hasn't filled it in yet


@dataclass(frozen=True)
class Result:
    usd_in: float
    usd_out: float
    ngn_in: float
    ngn_out: float
    # Cashed-out figures: only money that has left Polymarket.
    usd_profit: float  # usd_out - usd_in
    real_profit_ngn: float  # ngn_out - ngn_in
    avg_deposit_rate: float | None  # naira per dollar paid, weighted by size
    fx_effect_ngn: float | None  # real profit - usd_profit x avg_deposit_rate
    tax_ngn: float
    # "If you cashed out today": adds money still inside at today's rate.
    # None when the caller didn't supply both numbers.
    usd_inside: float | None
    total_profit_ngn: float | None


def estimate_tax(profit_ngn: float, rate: float) -> float:
    """Flat-rate tax on a positive profit. Losses owe nothing."""
    return max(profit_ngn, 0.0) * rate


def _validate(flows: list[Flow]) -> list[tuple[str, float, float]]:
    """Check every row; return (kind, usd, ngn) with kind normalised."""
    clean = []
    for i, f in enumerate(flows, start=1):
        kind = (f.kind or "").strip().lower()
        if kind not in (DEPOSIT, WITHDRAWAL):
            raise FlowError(f"Row {i}: type must be deposit or withdrawal, got {f.kind!r}.")
        if f.usd is None or f.usd <= 0:
            raise FlowError(f"Row {i}: dollar amount must be more than 0.")
        if f.ngn is None:
            raise FlowError(f"Row {i}: enter the naira you {'paid' if kind == DEPOSIT else 'received'}.")
        if f.ngn <= 0:
            raise FlowError(f"Row {i}: naira amount must be more than 0.")
        clean.append((kind, float(f.usd), float(f.ngn)))
    return clean


def calculate(
    flows: list[Flow],
    tax_rate: float = 0.10,
    usd_inside: float | None = None,
    today_rate: float | None = None,
) -> Result:
    """Work out naira in/out, real profit, FX effect and a rough tax estimate.

    FX effect = real naira profit - (dollar profit x average naira-per-dollar paid on deposits).
    It captures exchange-rate moves plus any fees or spreads baked into the naira amounts.

    Pass usd_inside (cash + open positions still in Polymarket) and today_rate
    (naira per dollar you could sell at today) to also get total_profit_ngn.

    Raises FlowError if any row is incomplete or invalid, so a missing naira
    amount can never be silently treated as zero.
    """
    rows = _validate(flows)

    usd_in = sum(u for k, u, _ in rows if k == DEPOSIT)
    usd_out = sum(u for k, u, _ in rows if k == WITHDRAWAL)
    ngn_in = sum(n for k, _, n in rows if k == DEPOSIT)
    ngn_out = sum(n for k, _, n in rows if k == WITHDRAWAL)

    usd_profit = usd_out - usd_in
    real_profit = ngn_out - ngn_in

    avg_rate = ngn_in / usd_in if usd_in else None
    fx_effect = real_profit - usd_profit * avg_rate if avg_rate is not None else None

    total_profit = None
    if usd_inside is not None and today_rate is not None:
        if usd_inside < 0 or today_rate <= 0:
            raise FlowError("Money inside can't be negative and today's rate must be more than 0.")
        total_profit = real_profit + usd_inside * today_rate

    return Result(
        usd_in=usd_in,
        usd_out=usd_out,
        ngn_in=ngn_in,
        ngn_out=ngn_out,
        usd_profit=usd_profit,
        real_profit_ngn=real_profit,
        avg_deposit_rate=avg_rate,
        fx_effect_ngn=fx_effect,
        tax_ngn=estimate_tax(real_profit, tax_rate),
        usd_inside=usd_inside,
        total_profit_ngn=total_profit,
    )