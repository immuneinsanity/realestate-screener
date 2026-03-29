import time
import pandas as pd
from datetime import datetime
from typing import List

from src.analyzer import enrich_properties, is_landlord_friendly
from src.db import upsert_properties, update_market_stats


PROPERTY_TYPE_FILTERS = {"SINGLE_FAMILY", "Single Family", "SingleFamily", "single_family"}

MIN_BEDS = 3
MIN_SQFT = 1250
MAX_PRICE = 125_000


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names from homeharvest output."""
    rename = {
        "full_street_line": "address",
        "street": "address",
        "list_price": "price",
        "beds_min": "beds",
        "baths_min": "baths",
        "sqft_min": "sqft",
        "square_feet": "sqft",
        "lot_sqft": "lot_sqft",
        "style": "property_type",
        "days_on_mls": "days_on_market",
        "mls_id": "mls_id",
        "zip_code": "zip_code",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    return df


def _filter_listings(df: pd.DataFrame) -> pd.DataFrame:
    """Apply investment criteria filters."""
    if df.empty:
        return df

    df = df.copy()

    # Normalize numeric columns
    for col in ["price", "beds", "sqft"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Status filter — must be active for sale
    if "status" in df.columns:
        df = df[df["status"].str.upper().isin(["FOR_SALE", "ACTIVE", "FORSALE"]) |
                df["status"].str.contains("SALE", na=False, case=False)]

    # Single family only
    if "property_type" in df.columns:
        pt = df["property_type"].str.upper().str.replace(" ", "_", regex=False)
        df = df[pt.str.contains("SINGLE|SFR|SFH", na=False, regex=True)]

    # Investment criteria
    if "price" in df.columns:
        df = df[df["price"].notna() & (df["price"] > 0) & (df["price"] <= MAX_PRICE)]
    if "beds" in df.columns:
        df = df[df["beds"].notna() & (df["beds"] >= MIN_BEDS)]
    if "sqft" in df.columns:
        df = df[df["sqft"].notna() & (df["sqft"] >= MIN_SQFT)]

    # Landlord-friendly state
    if "state" in df.columns:
        df = df[df["state"].apply(lambda s: is_landlord_friendly(str(s)))]

    return df.reset_index(drop=True)


def scrape_market(location: str, past_days: int = 30) -> pd.DataFrame:
    """
    Scrape listings for a single market using homeharvest.
    Returns enriched, filtered DataFrame. Returns empty DataFrame on failure.
    """
    try:
        from homeharvest import scrape_property
    except ImportError:
        print("homeharvest not installed. Run: pip install homeharvest")
        return pd.DataFrame()

    try:
        print(f"Scraping {location}...")
        raw = scrape_property(
            location=location,
            listing_type="for_sale",
            past_days=past_days,
        )
    except Exception as e:
        print(f"Error scraping {location}: {e}")
        return pd.DataFrame()

    if raw is None or raw.empty:
        print(f"No results for {location}")
        return pd.DataFrame()

    df = _normalize_columns(raw)
    df = _filter_listings(df)

    if df.empty:
        print(f"No listings passed filters for {location}")
        return pd.DataFrame()

    df = enrich_properties(df)

    # Persist to DB
    upsert_properties(df, market=location)
    update_market_stats(location, df)

    print(f"{location}: {len(df)} qualifying properties found")
    return df


def scrape_multiple_markets(
    locations: List[str],
    past_days: int = 30,
    delay: float = 1.5,
) -> pd.DataFrame:
    """
    Scrape multiple markets sequentially. Returns combined DataFrame.
    """
    all_dfs = []

    for loc in locations:
        df = scrape_market(loc, past_days=past_days)
        if not df.empty:
            df["market"] = loc
            all_dfs.append(df)
        time.sleep(delay)

    if not all_dfs:
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)
    return combined.sort_values("score", ascending=False).reset_index(drop=True)
