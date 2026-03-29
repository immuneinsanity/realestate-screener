import pandas as pd
import numpy as np

MAX_PRICE = 125_000
LANDLORD_FRIENDLY_STATES = {
    "TX", "FL", "AZ", "IN", "OH", "GA", "TN", "AL", "NC", "SC",
    "AR", "OK", "KY", "MO", "ID", "WY", "ND", "SD", "MT", "CO",
}

# 2024 3BR FMR values by state (hardcoded to avoid unreliable HUD URL)
STATE_FMR_3BR = {
    'AR': 950, 'TX': 1350, 'FL': 1650, 'AZ': 1450, 'IN': 950,
    'OH': 950, 'GA': 1250, 'TN': 1100, 'AL': 850, 'NC': 1150,
    'SC': 1050, 'OK': 950, 'KY': 900, 'MO': 950, 'ID': 1200,
    'WY': 1050, 'ND': 950, 'SD': 900, 'MT': 1100, 'CO': 1650,
}


def get_hud_fmr(state: str, county: str = "", city: str = "") -> float:
    """Look up 3BR FMR for a given state. Returns monthly rent estimate."""
    return STATE_FMR_3BR.get(state.strip().upper(), 900)


def calculate_1pct_rule(price: float, monthly_rent: float) -> float:
    """Returns rent/price ratio (e.g. 0.0125 = 1.25%)."""
    if price and price > 0:
        return monthly_rent / price
    return 0.0


def score_property(row: dict) -> dict:
    """
    Score a property 0-100:
      - 1% rule (0-40 pts)
      - Price (0-20 pts)
      - Size/sqft (0-20 pts)
      - Bedrooms (0-10 pts)
      - Days on market (0-10 pts)
    """
    breakdown = {}

    # --- 1% rule (40 pts) ---
    ratio = float(row.get("rent_ratio", 0) or 0)
    if ratio >= 0.01:
        rent_score = 40
    elif ratio >= 0.008:
        # Scale 20-40 between 0.8% and 1.0%
        rent_score = 20 + (ratio - 0.008) / 0.002 * 20
    elif ratio >= 0.006:
        # Scale 0-20 between 0.6% and 0.8%
        rent_score = (ratio - 0.006) / 0.002 * 20
    else:
        rent_score = 0
    breakdown["rent_ratio_score"] = round(rent_score, 1)

    # --- Price (20 pts): lower is better, max is MAX_PRICE ---
    price = float(row.get("price", 0) or 0)
    if 0 < price <= MAX_PRICE:
        price_score = (1 - price / MAX_PRICE) * 20
    else:
        price_score = 0
    breakdown["price_score"] = round(price_score, 1)

    # --- Size (20 pts): sqft above 1250 min ---
    sqft = float(row.get("sqft", 0) or 0)
    MIN_SQFT = 1250
    MAX_SQFT = 2500  # cap bonus at 2500 sqft
    if sqft >= MIN_SQFT:
        size_score = min((sqft - MIN_SQFT) / (MAX_SQFT - MIN_SQFT) * 20, 20)
    else:
        size_score = 0
    breakdown["size_score"] = round(size_score, 1)

    # --- Bedrooms (10 pts) ---
    beds = int(row.get("beds", 0) or 0)
    if beds >= 5:
        bed_score = 10
    elif beds == 4:
        bed_score = 9
    elif beds == 3:
        bed_score = 6
    else:
        bed_score = 0
    breakdown["bed_score"] = bed_score

    # --- Days on market (10 pts): fresher = better ---
    dom = int(row.get("days_on_market", 0) or 0)
    if dom < 30:
        dom_score = 10
    elif dom < 60:
        dom_score = 5
    else:
        dom_score = 0
    breakdown["dom_score"] = dom_score

    total = rent_score + price_score + size_score + bed_score + dom_score
    breakdown["total"] = round(total, 1)

    return breakdown


def enrich_properties(df: pd.DataFrame) -> pd.DataFrame:
    """Add est_rent, rent_ratio, and score columns to a listings DataFrame."""
    if df.empty:
        return df

    df = df.copy()

    # Ensure numeric columns
    for col in ["price", "beds", "sqft", "days_on_market"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    est_rents = []
    rent_ratios = []
    scores = []
    score_breakdowns = []

    for _, row in df.iterrows():
        state = str(row.get("state", ""))
        county = str(row.get("county", "") or "")
        city = str(row.get("city", "") or "")
        price = float(row.get("price", 0) or 0)

        est_rent = get_hud_fmr(state, county, city)
        ratio = calculate_1pct_rule(price, est_rent)

        row_dict = row.to_dict()
        row_dict["est_rent"] = est_rent
        row_dict["rent_ratio"] = ratio

        breakdown = score_property(row_dict)

        est_rents.append(est_rent)
        rent_ratios.append(ratio)
        scores.append(breakdown["total"])
        score_breakdowns.append(breakdown)

    df["est_rent"] = est_rents
    df["rent_ratio"] = rent_ratios
    df["score"] = scores
    df["score_breakdown"] = score_breakdowns

    return df


def is_landlord_friendly(state: str) -> bool:
    return state.strip().upper() in LANDLORD_FRIENDLY_STATES


def get_ratio_label(ratio: float) -> str:
    if ratio >= 0.01:
        return "🟢"
    elif ratio >= 0.008:
        return "🟡"
    else:
        return "🔴"
