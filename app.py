import math
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from calc import Flow, FlowError, calculate
from sources.polymarket import (
    PolymarketError,
    extract_flows,
    fetch_activity,
    fetch_value,
    is_valid_address,
)

st.set_page_config(page_title="Polymarket profit in Naira!", page_icon="₦")
st.title("Your real Polymarket profit in Naira!")
st.caption("No logins, no private keys, nothing saved.")


def blank_to_none(value):
    """Empty table cells arrive as NaN/None; calc.py needs None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def naira(value) -> str:
    if value is None:
        return "—"
    return f"-₦{-value:,.0f}" if value < 0 else f"₦{value:,.0f}"


def dollars(value) -> str:
    if value is None:
        return "—"
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"


address = st.text_input("Polymarket wallet address", placeholder="0x...")

if st.button("Fetch activity") and address:
    if not is_valid_address(address):
        st.error("That doesn't look like a wallet address (0x followed by 40 hex characters).")
    else:
        try:
            with st.spinner("Reading your Polymarket activity..."):
                activity, complete = fetch_activity(address)
                st.session_state["flows"] = extract_flows(activity)
                st.session_state["value_inside"] = fetch_value(address)
                st.session_state["n_activity"] = len(activity)
                st.session_state["history_complete"] = complete
        except PolymarketError as e:
            st.error(f"Couldn't read from Polymarket: {e}")

if "flows" in st.session_state:
    flows = st.session_state["flows"]
    st.write(f"Found {st.session_state['n_activity']} activity rows.")

    if not st.session_state["history_complete"]:
        st.warning(
            "Your history is very long and only the most recent part was read. "
            "Your earliest deposits may be missing: add them by hand below."
        )
    if not flows:
        st.info(
            "No deposits or withdrawals were found in the activity feed. "
            "Add them by hand below."
        )

    table = pd.DataFrame(
        [
            {
                "date": datetime.fromtimestamp(f["timestamp"], timezone.utc).date(),
                "kind": f["kind"],
                "usd": f["usd"],
                "naira": None,
            }
            for f in flows
        ],
        columns=["date", "kind", "usd", "naira"],
    )

    st.subheader("1. Naira paid / received")
    st.caption("Fill in every row. Fix or add the dollar amount if it's empty.")
    edited = st.data_editor(
        table,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "date": st.column_config.DateColumn("Date"),
            "kind": st.column_config.SelectboxColumn(
                "Type", options=["deposit", "withdrawal"], required=True
            ),
            "usd": st.column_config.NumberColumn("USD", min_value=0.0, format="$%.2f"),
            "naira": st.column_config.NumberColumn(
                "Naira (paid for deposit / received for withdrawal)",
                min_value=0.0,
                format="₦%.2f",
            ),
        },
    )

    st.subheader("2. Money still inside Polymarket")
    usd_inside = st.number_input(
        "Value still inside (USD)",
        min_value=0.0,
        value=float(st.session_state["value_inside"]),
        step=1.0,
        help="Pre-filled from your open positions. Check it matches your Polymarket "
        "balance, and add any unspent cash.",
    )
    today_rate = st.number_input(
        "Today's rate you could sell at (₦ per $)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        help="Leave at 0 to skip the 'if you cashed out today' figure.",
    )

    tax_pct = st.slider(
        "Tax rate for the estimate (%)", 0, 30, 10,
        help="Placeholder flat rate. Check what applies to you.",
    )

    rows = [
        Flow(
            kind=blank_to_none(r.kind) or "",
            usd=blank_to_none(r.usd),
            ngn=blank_to_none(r.naira),
        )
        for r in edited.itertuples()
    ]

    if not rows:
        st.info("Add at least one deposit to see your results.")
    else:
        try:
            r = calculate(
                rows,
                tax_rate=tax_pct / 100,
                usd_inside=usd_inside if today_rate > 0 else None,
                today_rate=today_rate if today_rate > 0 else None,
            )
        except FlowError as e:
            st.warning(f"{e} Results appear once every row is complete.")
        else:
            st.subheader("3. Your results")
            c1, c2, c3 = st.columns(3)
            c1.metric("Naira in", naira(r.ngn_in))
            c2.metric("Naira out", naira(r.ngn_out))
            c3.metric("Cashed-out profit", naira(r.real_profit_ngn))

            c4, c5, c6 = st.columns(3)
            c4.metric("Cashed-out dollar profit", dollars(r.usd_profit))
            c5.metric("FX & fees effect", naira(r.fx_effect_ngn))
            c6.metric("Rough tax estimate", naira(r.tax_ngn))

            if r.total_profit_ngn is not None:
                st.metric("Total profit if you cashed out today", naira(r.total_profit_ngn))
            st.caption(
                "Cashed-out figures count only money that has left Polymarket. "
                "Enter today's rate above to include money still inside."
            )

st.caption("Not affiliated with Polymarket. Not financial or tax advice.")