import pandas as pd
import numpy as np

MAX_PRICE = 125_000

# Crime tiers: 1=Very Safe, 2=Safe, 3=Moderate, 4=High Crime, 5=Very High Crime
# Based on FBI crime data and NeighborhoodScout
CITY_CRIME_TIERS = {
    # AR
    'little rock': 5, 'fayetteville': 2, 'fort smith': 4, 'jonesboro': 3,
    'springdale': 2, 'rogers': 1,
    # TX
    'houston': 4, 'dallas': 4, 'san antonio': 3, 'fort worth': 3,
    'el paso': 3, 'lubbock': 4, 'amarillo': 3, 'waco': 4,
    'abilene': 3, 'beaumont': 4, 'laredo': 4,
    # TN
    'memphis': 5, 'nashville': 3, 'knoxville': 3, 'chattanooga': 3,
    'jackson': 4, 'clarksville': 3,
    # AL
    'birmingham': 5, 'huntsville': 3, 'montgomery': 5, 'mobile': 4,
    'tuscaloosa': 4,
    # OH
    'cleveland': 5, 'columbus': 3, 'cincinnati': 4, 'dayton': 4,
    'toledo': 4, 'akron': 4, 'youngstown': 5,
    # GA
    'atlanta': 4, 'macon': 5, 'augusta': 4, 'savannah': 4,
    # FL
    'jacksonville': 4, 'tampa': 3, 'orlando': 3, 'pensacola': 3,
    'ocala': 3, 'gainesville': 3,
    # IN
    'indianapolis': 4, 'fort wayne': 3, 'south bend': 4,
    'evansville': 3, 'muncie': 4,
    # NC
    'charlotte': 3, 'greensboro': 4, 'winston-salem': 4,
    'durham': 3, 'raleigh': 2,
    # SC
    'columbia': 4, 'greenville': 3, 'spartanburg': 4,
    'rock hill': 3, 'florence': 4,
    # OK
    'oklahoma city': 4, 'tulsa': 4, 'lawton': 4,
    'norman': 2, 'broken arrow': 2,
    # KY
    'louisville': 4, 'lexington': 3, 'bowling green': 3,
    'owensboro': 3, 'covington': 4,
    # MO
    'kansas city': 4, 'st. louis': 5, 'springfield': 3,
    'independence': 3, 'joplin': 3,
}

_CRIME_LABELS = {1: '🟢 Very Safe', 2: '🟢 Safe', 3: '🟡 Moderate', 4: '🔴 High Crime', 5: '🔴 Very High'}


def get_crime_tier(city: str) -> tuple:
    """Returns (tier, label) where tier 1=safest, 5=most dangerous."""
    tier = CITY_CRIME_TIERS.get(city.lower().strip(), 3)
    return tier, _CRIME_LABELS[tier]
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
      - 1% rule (0-35 pts)
      - Crime (0-20 pts)
      - Price (0-15 pts)
      - Size/sqft (0-15 pts)
      - Bedrooms (0-8 pts)
      - Days on market (0-7 pts)
    """
    breakdown = {}

    # --- 1% rule (35 pts) ---
    ratio = float(row.get("rent_ratio", 0) or 0)
    if ratio >= 0.01:
        rent_score = 35
    elif ratio >= 0.008:
        rent_score = 17.5 + (ratio - 0.008) / 0.002 * 17.5
    elif ratio >= 0.006:
        rent_score = (ratio - 0.006) / 0.002 * 17.5
    else:
        rent_score = 0
    breakdown["rent_ratio_score"] = round(rent_score, 1)

    # --- Crime (20 pts): tier 1=20pts, tier 5=0pts ---
    crime_tier = int(row.get("crime_tier", 3) or 3)
    crime_pts = {1: 20, 2: 15, 3: 10, 4: 5, 5: 0}
    crime_score = crime_pts.get(crime_tier, 10)
    breakdown["crime_score"] = crime_score

    # --- Price (15 pts): lower is better, max is MAX_PRICE ---
    price = float(row.get("price", 0) or 0)
    if 0 < price <= MAX_PRICE:
        price_score = (1 - price / MAX_PRICE) * 15
    else:
        price_score = 0
    breakdown["price_score"] = round(price_score, 1)

    # --- Size (15 pts): sqft above 1250 min ---
    sqft = float(row.get("sqft", 0) or 0)
    MIN_SQFT = 1250
    MAX_SQFT = 2500
    if sqft >= MIN_SQFT:
        size_score = min((sqft - MIN_SQFT) / (MAX_SQFT - MIN_SQFT) * 15, 15)
    else:
        size_score = 0
    breakdown["size_score"] = round(size_score, 1)

    # --- Bedrooms (8 pts) ---
    beds = int(row.get("beds", 0) or 0)
    if beds >= 5:
        bed_score = 8
    elif beds == 4:
        bed_score = 7
    elif beds == 3:
        bed_score = 5
    else:
        bed_score = 0
    breakdown["bed_score"] = bed_score

    # --- Days on market (7 pts): fresher = better ---
    dom = int(row.get("days_on_market", 0) or 0)
    if dom < 30:
        dom_score = 7
    elif dom < 60:
        dom_score = 3
    else:
        dom_score = 0
    breakdown["dom_score"] = dom_score

    total = rent_score + crime_score + price_score + size_score + bed_score + dom_score
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
    crime_tiers = []
    crime_labels = []

    for _, row in df.iterrows():
        state = str(row.get("state", ""))
        county = str(row.get("county", "") or "")
        city = str(row.get("city", "") or "")
        price = float(row.get("price", 0) or 0)

        est_rent = get_hud_fmr(state, county, city)
        ratio = calculate_1pct_rule(price, est_rent)
        tier, label = get_crime_tier(city)

        row_dict = row.to_dict()
        row_dict["est_rent"] = est_rent
        row_dict["rent_ratio"] = ratio
        row_dict["crime_tier"] = tier

        breakdown = score_property(row_dict)

        est_rents.append(est_rent)
        rent_ratios.append(ratio)
        scores.append(breakdown["total"])
        score_breakdowns.append(breakdown)
        crime_tiers.append(tier)
        crime_labels.append(label)

    df["est_rent"] = est_rents
    df["rent_ratio"] = rent_ratios
    df["score"] = scores
    df["score_breakdown"] = score_breakdowns
    df["crime_tier"] = crime_tiers
    df["crime_label"] = crime_labels

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
