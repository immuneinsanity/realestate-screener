# Real Estate Investment Screener

A Streamlit web app for finding single-family homes to buy as rental investments. Screens Realtor.com listings against the 1% rule using HUD Fair Market Rents.

## Investment Criteria

| Criterion | Value |
|-----------|-------|
| Max Price | $125,000 |
| Min Bedrooms | 3+ |
| Min Square Footage | 1,250 sqft |
| Rent Rule | Monthly rent ≥ 1% of purchase price |
| States | Landlord-friendly states only |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the app

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

## Usage

### Screener Tab
1. Select a market from the sidebar dropdown (or type a custom city, state)
2. Adjust filters: max price, min beds, min sqft, min rent ratio
3. Click **🔍 Scan Market** — pulls live listings from Realtor.com
4. Properties are scored 0–100 and sorted by score
5. Expand any property for full details, links, and score breakdown
6. Click **📌 Add to Watchlist** to save a property

### Watchlist Tab
- Track saved properties with statuses: Researching / Made Offer / Under Contract / Passed
- Add notes to each property
- Export to CSV

### Market Analysis Tab
- Compare scanned markets side by side
- Charts: avg price, avg rent ratio, qualifying property counts, price vs. ratio scatter

## Scoring (0–100)

| Component | Max Points | Logic |
|-----------|-----------|-------|
| 1% Rule | 40 | ratio ≥ 1% = 40pts; scales linearly below |
| Price | 20 | Lower price relative to $125k cap = more points |
| Size | 20 | Sqft above 1,250 min, capped at 2,500 |
| Bedrooms | 10 | 3BR=6, 4BR=9, 5BR+=10 |
| Days on Market | 10 | <30 days=10, 30-60=5, 60+=0 |

## Data Sources

- **Listings**: Realtor.com via [homeharvest](https://github.com/Bunsly/HomeHarvest)
- **Rent Estimates**: HUD Fair Market Rents 2024 (auto-downloaded on first run)
- **Landlord-friendly states**: Hardcoded list based on tenant law research

## Landlord-Friendly States

TX, FL, AZ, IN, OH, GA, TN, AL, NC, SC, AR, OK, KY, MO, ID, WY, ND, SD, MT, CO

## File Structure

```
realestate-screener/
├── app.py              # Main Streamlit app
├── requirements.txt
├── README.md
├── data/
│   ├── screener.db         # SQLite database (auto-created)
│   └── hud_fmr_2024.csv    # HUD FMR data (auto-downloaded)
└── src/
    ├── __init__.py
    ├── scraper.py      # homeharvest scraping + filtering
    ├── analyzer.py     # FMR lookup, scoring, 1% rule
    └── db.py           # SQLite CRUD operations
```

## Notes

- Scraping is rate-limited by homeharvest — scanning a market takes 30–60 seconds
- Results are cached in SQLite; re-scanning a market updates existing records
- HUD FMR data is downloaded once on first run (~15MB Excel file)
- The 1% rule is a screening heuristic, not a guarantee of cash flow
