import sqlite3
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "screener.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mls_id TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            county TEXT,
            price REAL,
            beds INTEGER,
            baths REAL,
            sqft REAL,
            lot_sqft REAL,
            property_type TEXT,
            status TEXT,
            days_on_market INTEGER,
            list_date TEXT,
            year_built INTEGER,
            hoa_fee REAL,
            tax_amount REAL,
            latitude REAL,
            longitude REAL,
            url TEXT,
            property_url TEXT,
            est_rent REAL,
            rent_ratio REAL,
            score REAL,
            score_breakdown TEXT,
            market TEXT,
            scraped_at TEXT,
            UNIQUE(mls_id, market)
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            mls_id TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            price REAL,
            beds INTEGER,
            sqft REAL,
            est_rent REAL,
            rent_ratio REAL,
            score REAL,
            url TEXT,
            notes TEXT,
            status TEXT DEFAULT 'Researching',
            added_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT UNIQUE,
            last_scraped TEXT,
            property_count INTEGER DEFAULT 0,
            avg_price REAL,
            avg_rent_ratio REAL,
            qualifying_count INTEGER DEFAULT 0
        );
    """)

    conn.commit()

    # Migrations for existing DBs
    for migration in [
        "ALTER TABLE properties ADD COLUMN property_url TEXT",
    ]:
        try:
            cur.execute(migration)
            conn.commit()
        except Exception:
            pass  # column already exists

    conn.close()


def upsert_properties(df: pd.DataFrame, market: str):
    if df.empty:
        return 0

    conn = get_connection()
    now = datetime.now().isoformat()
    inserted = 0

    for _, row in df.iterrows():
        score_breakdown = row.get("score_breakdown", {})
        if isinstance(score_breakdown, dict):
            score_breakdown = json.dumps(score_breakdown)

        try:
            conn.execute("""
                INSERT INTO properties (
                    mls_id, address, city, state, zip_code, county, price, beds, baths,
                    sqft, lot_sqft, property_type, status, days_on_market, list_date,
                    year_built, hoa_fee, tax_amount, latitude, longitude, url, property_url,
                    est_rent, rent_ratio, score, score_breakdown, market, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mls_id, market) DO UPDATE SET
                    price=excluded.price,
                    days_on_market=excluded.days_on_market,
                    property_url=excluded.property_url,
                    est_rent=excluded.est_rent,
                    rent_ratio=excluded.rent_ratio,
                    score=excluded.score,
                    score_breakdown=excluded.score_breakdown,
                    scraped_at=excluded.scraped_at
            """, (
                str(row.get("mls_id", "")),
                str(row.get("address", "")),
                str(row.get("city", "")),
                str(row.get("state", "")),
                str(row.get("zip_code", "")),
                str(row.get("county", "")),
                float(row.get("price", 0) or 0),
                int(row.get("beds", 0) or 0),
                float(row.get("baths", 0) or 0),
                float(row.get("sqft", 0) or 0),
                float(row.get("lot_sqft", 0) or 0),
                str(row.get("property_type", "")),
                str(row.get("status", "")),
                int(row.get("days_on_market", 0) or 0),
                str(row.get("list_date", "")),
                int(row.get("year_built", 0) or 0),
                float(row.get("hoa_fee", 0) or 0),
                float(row.get("tax_amount", 0) or 0),
                float(row.get("latitude", 0) or 0),
                float(row.get("longitude", 0) or 0),
                str(row.get("url", "")),
                str(row.get("property_url", "") or row.get("permalink", "") or ""),
                float(row.get("est_rent", 0) or 0),
                float(row.get("rent_ratio", 0) or 0),
                float(row.get("score", 0) or 0),
                score_breakdown,
                market,
                now,
            ))
            inserted += 1
        except Exception:
            pass

    conn.commit()
    conn.close()
    return inserted


def get_properties(market=None, filters: dict = None) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM properties WHERE 1=1"
    params = []

    if market:
        if isinstance(market, list):
            placeholders = ",".join("?" * len(market))
            query += f" AND market IN ({placeholders})"
            params.extend(market)
        else:
            query += " AND market = ?"
            params.append(market)

    if filters:
        if filters.get("max_price"):
            query += " AND price <= ?"
            params.append(filters["max_price"])
        if filters.get("min_beds"):
            query += " AND beds >= ?"
            params.append(filters["min_beds"])
        if filters.get("min_sqft"):
            query += " AND sqft >= ?"
            params.append(filters["min_sqft"])
        if filters.get("min_ratio"):
            query += " AND rent_ratio >= ?"
            params.append(filters["min_ratio"])

    query += " ORDER BY score DESC"

    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()

    return df


def get_all_properties(filters: dict = None) -> pd.DataFrame:
    return get_properties(market=None, filters=filters)


def update_market_stats(market: str, df: pd.DataFrame):
    if df.empty:
        return

    conn = get_connection()
    now = datetime.now().isoformat()

    qualifying = df[df["rent_ratio"] >= 0.01] if "rent_ratio" in df.columns else pd.DataFrame()

    conn.execute("""
        INSERT INTO markets (location, last_scraped, property_count, avg_price, avg_rent_ratio, qualifying_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(location) DO UPDATE SET
            last_scraped=excluded.last_scraped,
            property_count=excluded.property_count,
            avg_price=excluded.avg_price,
            avg_rent_ratio=excluded.avg_rent_ratio,
            qualifying_count=excluded.qualifying_count
    """, (
        market,
        now,
        len(df),
        float(df["price"].mean()) if "price" in df.columns else 0,
        float(df["rent_ratio"].mean()) if "rent_ratio" in df.columns else 0,
        len(qualifying),
    ))

    conn.commit()
    conn.close()


def get_markets() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM markets ORDER BY last_scraped DESC", conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def add_to_watchlist(prop: dict) -> bool:
    conn = get_connection()
    now = datetime.now().isoformat()
    try:
        conn.execute("""
            INSERT INTO watchlist (
                property_id, mls_id, address, city, state, price, beds, sqft,
                est_rent, rent_ratio, score, url, notes, status, added_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prop.get("id"),
            prop.get("mls_id", ""),
            prop.get("address", ""),
            prop.get("city", ""),
            prop.get("state", ""),
            prop.get("price", 0),
            prop.get("beds", 0),
            prop.get("sqft", 0),
            prop.get("est_rent", 0),
            prop.get("rent_ratio", 0),
            prop.get("score", 0),
            prop.get("url", ""),
            prop.get("notes", ""),
            prop.get("status", "Researching"),
            now,
            now,
        ))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_watchlist() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM watchlist ORDER BY added_at DESC", conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def update_watchlist_item(item_id: int, notes: str, status: str):
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE watchlist SET notes=?, status=?, updated_at=? WHERE id=?",
        (notes, status, now, item_id)
    )
    conn.commit()
    conn.close()


def remove_from_watchlist(item_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM watchlist WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
