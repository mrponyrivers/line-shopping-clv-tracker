# Line Shopping + CLV Tracker (Streamlit)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Live%20Demo-red)

A Streamlit app that helps you **shop the best line across books** and track **CLV (Closing Line Value)** over time.

---

## Live demo

✅ Open the app: https://mrponyrivers-line-shopping-clv-tracker.streamlit.app/

---
## Screenshots

![Line Shop](docs/screenshots/screenshot1.png)
![Best Prices + Selected Offer](docs/screenshots/screenshot2.png)
![CLV Tracker](docs/screenshots/screenshot3.png)
---
## What this app does

- **Line Shop:** log offers across books → automatically surface the **best price**
- **CLV Tracker:** log bets → update closing odds/line → compute CLV (beat-the-close)
- **Export-friendly:** download clean CSVs for analysis or integration

---

## Try it fast (30 seconds)

1) Open the **Live demo**
2) Click **Load demo** (sidebar) to populate sample offers + bets
3) Go to **CLV Tracker** → see CLV metrics + chart
4) Go to **Import / Export** → download templates + exports

---

## Quickstart

```bash
git clone https://github.com/mrponyrivers/line-shopping-clv-tracker.git
cd line-shopping-clv-tracker

python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows PowerShell

pip install -r requirements.txt
streamlit run app.py
```
---
## CSV formats

### Offers CSV (line shopping)

Recommended columns:
- `sport`, `league`, `game`
- `market_type` (ML/Spread/Total)
- `side` (team / Over / Under)
- `line` (optional numeric)
- `odds_decimal`
- `book`
- `notes` (optional)

### Bets CSV (CLV tracking)

Recommended columns:
- `sport`, `league`, `game`
- `market_type` (ML/Spread/Total)
- `direction` (Over/Under for totals, optional)
- `side`
- `entry_line`, `entry_odds_decimal`, `entry_book`
- `close_line`, `close_odds_decimal`
- `stake`, `fair_prob`, `result`, `notes` (optional)

---

## Why this matters (skills demonstrated)

This project demonstrates an end-to-end **sports odds + decisioning workflow**:  
line ingestion → normalization (decimal odds) → best-price selection → CLV measurement → exportable artifacts.

Built with a clean Streamlit UI and zero-friction templates for fast demos.

---

## Responsible note

This app is educational and workflow-focused. Betting involves risk and variance.  
CLV is a process metric (beating the close), not a guarantee of short-term profit.
