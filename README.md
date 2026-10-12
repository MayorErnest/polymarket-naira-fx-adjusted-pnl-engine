# polymarket-naira-fx-adjusted-pnl-engine

**See your real Polymarket profit in naira.**

Polymarket shows your profit in dollars. But you pay in naira and cash out in naira, and the exchange rate and fees on those days change what you really made. This tool shows the true number.

> Status: early development.

## Example

- You deposit **₦150,000** ($100).
- You trade and withdraw **$120**, which gives you **₦165,000** after fees.
- Polymarket says you made **$20**. Your real profit is **₦15,000**.

## How it works

1. Paste your Polymarket wallet address. The app reads your activity from Polymarket's public API.
2. Enter what you paid and received in naira.
3. Get your real naira profit and a rough tax estimate.

No logins, no private keys, nothing saved.

## Setup

```bash
git clone https://github.com/<your-username>/polymarket-naira-fx-adjusted-pnl-engine.git
cd polymarket-naira-fx-adjusted-pnl-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Disclaimer

Not affiliated with Polymarket. Not financial or tax advice; the tax figure is only an estimate.

## License

Copyright © 2026. All rights reserved.