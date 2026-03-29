import os
import requests
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
FMR_CSV = DATA_DIR / "hud_fmr_2024.csv"
FMR_XLSX_URL = "https://www.huduser.gov/portal/datasets/fmr/fmr2024/FY2024_4050_FMRs_rev.xlsx"

MAX_PRICE = 125_000
LANDLORD_FRIENDLY_STATES = {
    "TX", "FL", "AZ", "IN", "OH", "GA", "TN", "AL", "NC", "SC",
    "AR", "OK", "KY", "MO", "ID", "WY", "ND", "SD", "MT", "CO",
}

# Fallback rent estimates (3BR) by state when FMR lookup fails
STATE_FALLBACK_RENTS = {
    "AR": 850, "TX": 1100, "AL": 850, "TN": 950, "GA": 1050,
    "NC": 1000, "SC": 950, "OK": 850, "KY": 850, "MO": 900,
    "IN": 900, "OH": 950, "FL": 1200, "AZ": 1150, "CO": 1400,
    "ID": 1050, "WY": 950, "ND": 900, "SD": 850, "MT": 950,
}


def download_hud_fmr(force: bool = False) -> bool:
    """Download HUD FMR 2024 Excel file and save as CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if FMR_CSV.exists() and not force:
        return True

    try:
        print("Downloading HUD FMR 2024 data...")
        resp = requests.get(FMR_XLSX_URL, timeout=60, stream=True)
        resp.raise_for_status()

        xlsx_path = DATA_DIR / "FY2024_4050_FMRs_rev.xlsx"
        with open(xlsx_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        df = pd.read_excel(xlsx_path, engine="openpyxl")
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # Identify the columns we need — HUD names vary by year
        col_map = {}
        for col in df.columns:
            if "state" in col and "name" not in col and "abbr" not in col and len(col) < 12:
                col_map["state"] = col
            elif col in ("statename", "state_name", "state_alpha"):
                col_map["state_name"] = col
            elif "county" in col and "name" in col:
                col_map["county"] = col
            elif col in ("areaname", "area_name", "metro_area", "area_name24"):
                col_map["area_name"] = col
            elif "fmr_3" in col or col == "fmr3":
                col_map["fmr_3"] = col
            elif "fmr_2" in col or col == "fmr2":
                col_map["fmr_2"] = col

        # Build a clean dataframe
        rows = []
        for _, row in df.iterrows():
            state = str(row.get(col_map.get("state", ""), "")).strip().upper()
            if not state or state == "NAN":
                continue

            county = str(row.get(col_map.get("county", ""), "")).strip()
            area_name = str(row.get(col_map.get("area_name", ""), "")).strip()
            fmr_3 = row.get(col_map.get("fmr_3", ""), None)
            fmr_2 = row.get(col_map.get("fmr_2", ""), None)

            try:
                fmr_3 = float(fmr_3) if fmr_3 and str(fmr_3) != "nan" else None
                fmr_2 = float(fmr_2) if fmr_2 and str(fmr_2) != "nan" else None
            except (ValueError, TypeError):
                fmr_3 = None
                fmr_2 = None

            rows.append({
                "state": state,
                "county": county,
                "area_name": area_name,
                "fmr_3br": fmr_3,
                "fmr_2br": fmr_2,
            })

        out_df = pd.DataFrame(rows)
        out_df.to_csv(FMR_CSV, index=False)
        print(f"HUD FMR data saved: {len(out_df)} records")
        return True

    except Exception as e:
        print(f"Failed to download HUD FMR data: {e}")
        # Create a fallback CSV with state-level estimates
        _create_fallback_fmr()
        return False


def _create_fallback_fmr():
    """Create a minimal fallback FMR CSV from hardcoded state averages."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = [
        {"state": state, "county": "", "area_name": "", "fmr_3br": rent, "fmr_2br": int(rent * 0.82)}
        for state, rent in STATE_FALLBACK_RENTS.items()
    ]
    pd.DataFrame(rows).to_csv(FMR_CSV, index=False)


def _load_fmr_df() -> pd.DataFrame:
    if not FMR_CSV.exists():
        download_hud_fmr()
    if not FMR_CSV.exists():
        _create_fallback_fmr()
    try:
        df = pd.read_csv(FMR_CSV, dtype=str)
        df["state"] = df["state"].str.strip().str.upper()
        df["county"] = df["county"].str.strip().str.lower().fillna("")
        df["area_name"] = df["area_name"].str.strip().str.lower().fillna("")
        df["fmr_3br"] = pd.to_numeric(df["fmr_3br"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


_fmr_cache: pd.DataFrame = None


def get_fmr_df() -> pd.DataFrame:
    global _fmr_cache
    if _fmr_cache is None or _fmr_cache.empty:
        _fmr_cache = _load_fmr_df()
    return _fmr_cache


def get_hud_fmr(state: str, county: str = "", city: str = "") -> float:
    """Look up 3BR FMR for a given state/county. Returns monthly rent estimate."""
    df = get_fmr_df()
    if df.empty:
        return STATE_FALLBACK_RENTS.get(state.upper(), 900)

    state_upper = state.strip().upper()
    county_lower = county.strip().lower()
    city_lower = city.strip().lower()

    state_df = df[df["state"] == state_upper]
    if state_df.empty:
        return STATE_FALLBACK_RENTS.get(state_upper, 900)

    # Try exact county match
    if county_lower:
        county_clean = county_lower.replace(" county", "").replace(" parish", "").strip()
        match = state_df[state_df["county"].str.contains(county_clean, na=False, regex=False)]
        if not match.empty:
            val = match["fmr_3br"].dropna()
            if not val.empty:
                return float(val.iloc[0])

    # Try city match in area_name
    if city_lower:
        city_clean = city_lower.split(",")[0].strip()
        match = state_df[state_df["area_name"].str.contains(city_clean, na=False, regex=False)]
        if not match.empty:
            val = match["fmr_3br"].dropna()
            if not val.empty:
                return float(val.iloc[0])

    # State average
    state_avg = state_df["fmr_3br"].dropna()
    if not state_avg.empty:
        return float(state_avg.mean())

    return STATE_FALLBACK_RENTS.get(state_upper, 900)


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
