import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.db import (
    init_db,
    get_properties,
    get_all_properties,
    get_markets,
    add_to_watchlist,
    get_watchlist,
    update_watchlist_item,
    remove_from_watchlist,
)
from src.scraper import scrape_market
from src.analyzer import get_ratio_label, MAX_PRICE

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Real Estate Investment Screener",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Dark theme CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Base dark theme */
:root {
    --bg-primary: #0e1117;
    --bg-secondary: #1a1d27;
    --bg-card: #1e2130;
    --bg-hover: #252840;
    --accent: #4f8ef7;
    --accent-hover: #6fa3f9;
    --text-primary: #e8eaf0;
    --text-secondary: #9da3b4;
    --text-muted: #6b7280;
    --border: #2d3147;
    --success: #22c55e;
    --warning: #f59e0b;
    --danger: #ef4444;
    --score-high: #22c55e;
    --score-mid: #f59e0b;
    --score-low: #ef4444;
}

.stApp {
    background-color: var(--bg-primary);
    color: var(--text-primary);
}

[data-testid="stSidebar"] {
    background-color: var(--bg-secondary);
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label {
    color: var(--text-primary) !important;
}

/* Headers */
h1, h2, h3, h4 { color: var(--text-primary) !important; }

h1 {
    font-size: 1.8rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}

/* Metric cards */
[data-testid="metric-container"] {
    background-color: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.2rem;
}

[data-testid="metric-container"] label {
    color: var(--text-secondary) !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, var(--accent), #3d6fd4);
    color: white !important;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.5rem 1.5rem;
    transition: all 0.2s;
}

.stButton > button:hover {
    background: linear-gradient(135deg, var(--accent-hover), #4f7fe4);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(79, 142, 247, 0.3);
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}

/* Tabs */
[data-testid="stTabs"] [role="tablist"] {
    gap: 4px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0;
}

[data-testid="stTabs"] [role="tab"] {
    background: transparent;
    border: none;
    color: var(--text-secondary) !important;
    font-weight: 500;
    padding: 0.6rem 1.2rem;
    border-radius: 8px 8px 0 0;
}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    background: var(--bg-card);
    color: var(--text-primary) !important;
    border-bottom: 2px solid var(--accent);
}

/* Expander */
[data-testid="stExpander"] {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
}

/* Input fields */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div,
.stMultiSelect > div > div {
    background-color: var(--bg-secondary) !important;
    border-color: var(--border) !important;
    color: var(--text-primary) !important;
}

/* Info/success/warning boxes */
.stAlert {
    background-color: var(--bg-card) !important;
    border-color: var(--border) !important;
    color: var(--text-primary) !important;
}

/* Score badge styles */
.score-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.85rem;
}
.score-high { background: rgba(34,197,94,0.2); color: #22c55e; }
.score-mid  { background: rgba(245,158,11,0.2); color: #f59e0b; }
.score-low  { background: rgba(239,68,68,0.2); color: #ef4444; }

/* Property card */
.prop-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 0.8rem;
    transition: border-color 0.2s;
}
.prop-card:hover { border-color: var(--accent); }

/* Sidebar divider */
.sidebar-section {
    margin-top: 1.2rem;
    padding-top: 1.2rem;
    border-top: 1px solid var(--border);
}

div[data-testid="stVerticalBlock"] > div {
    gap: 0.4rem;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants & init
# ---------------------------------------------------------------------------
DEFAULT_MARKETS = [
    # AR
    "Little Rock, AR", "Fayetteville, AR", "Fort Smith, AR", "Jonesboro, AR", "Springdale, AR",
    # TX
    "Dallas, TX", "Houston, TX", "San Antonio, TX", "Fort Worth, TX", "El Paso, TX",
    "Lubbock, TX", "Amarillo, TX", "Waco, TX", "Abilene, TX",
    # FL
    "Jacksonville, FL", "Tampa, FL", "Orlando, FL", "Pensacola, FL", "Ocala, FL",
    # AZ
    "Tucson, AZ", "Yuma, AZ", "Sierra Vista, AZ", "Flagstaff, AZ", "Prescott, AZ",
    # IN
    "Indianapolis, IN", "Fort Wayne, IN", "South Bend, IN", "Evansville, IN", "Muncie, IN",
    # OH
    "Cleveland, OH", "Columbus, OH", "Cincinnati, OH", "Dayton, OH", "Toledo, OH",
    "Akron, OH", "Youngstown, OH",
    # GA
    "Macon, GA", "Augusta, GA", "Savannah, GA", "Columbus, GA", "Albany, GA",
    # TN
    "Memphis, TN", "Knoxville, TN", "Chattanooga, TN", "Jackson, TN", "Clarksville, TN",
    # AL
    "Birmingham, AL", "Huntsville, AL", "Montgomery, AL", "Mobile, AL", "Tuscaloosa, AL",
    # NC
    "Greensboro, NC", "Winston-Salem, NC", "Durham, NC", "Fayetteville, NC", "Concord, NC",
    # SC
    "Columbia, SC", "Greenville, SC", "Spartanburg, SC", "Rock Hill, SC", "Florence, SC",
    # OK
    "Oklahoma City, OK", "Tulsa, OK", "Lawton, OK", "Norman, OK", "Broken Arrow, OK",
    # KY
    "Louisville, KY", "Lexington, KY", "Bowling Green, KY", "Owensboro, KY", "Covington, KY",
    # MO
    "Kansas City, MO", "St. Louis, MO", "Springfield, MO", "Independence, MO", "Joplin, MO",
    # ID
    "Boise, ID", "Nampa, ID", "Meridian, ID", "Pocatello, ID", "Idaho Falls, ID",
    # CO
    "Colorado Springs, CO", "Pueblo, CO", "Fort Collins, CO",
    # MT
    "Billings, MT", "Missoula, MT", "Great Falls, MT", "Bozeman, MT",
    # WY
    "Cheyenne, WY", "Casper, WY",
    # ND
    "Fargo, ND", "Bismarck, ND", "Grand Forks, ND",
    # SD
    "Sioux Falls, SD", "Rapid City, SD", "Aberdeen, SD",
]

WATCHLIST_STATUSES = ["Researching", "Made Offer", "Under Contract", "Passed"]

init_db()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏠 Investment Screener")
    st.markdown("*Single-family rental finder*")

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("**Scan Market**")

    all_markets = DEFAULT_MARKETS.copy()
    custom_raw = st.text_input(
        "Add custom market",
        placeholder="e.g. Memphis, TN",
        key="custom_market_input",
        label_visibility="collapsed",
    )
    if custom_raw and custom_raw.strip() not in all_markets:
        all_markets.append(custom_raw.strip())

    selected_market = st.selectbox(
        "Select market to scan",
        all_markets,
        key="selected_market",
        label_visibility="collapsed",
    )

    st.markdown("**View Markets**")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("Select All", key="markets_select_all", use_container_width=True):
            st.session_state["markets_view"] = all_markets.copy()
    with btn_col2:
        if st.button("Select None", key="markets_select_none", use_container_width=True):
            st.session_state["markets_view"] = []

    if "markets_view" not in st.session_state:
        st.session_state["markets_view"] = []

    selected_markets = st.multiselect(
        "Markets to display",
        all_markets,
        key="markets_view",
        label_visibility="collapsed",
        placeholder="Select markets to display…",
    )

    past_days = st.slider("Listings from last N days", 7, 90, 30, key="past_days")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("**Filters**")
    max_price = st.number_input(
        "Max Price ($)", value=MAX_PRICE, step=5_000, min_value=50_000, max_value=250_000
    )
    min_beds = st.selectbox("Min Bedrooms", [3, 4, 5], index=0)
    min_sqft = st.number_input("Min Sqft", value=1250, step=50, min_value=800, max_value=3000)
    min_ratio = st.slider(
        "Min Rent Ratio (%)", min_value=0.0, max_value=2.0, value=1.0, step=0.1
    ) / 100
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    scan_btn = st.button("🔍 Scan Market", use_container_width=True, type="primary")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.caption(f"Criteria: ≤${max_price:,} · {min_beds}+ bed · {min_sqft:,}+ sqft")
    st.caption("Data: Realtor.com via homeharvest · HUD FMR rents")
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Scan action
# ---------------------------------------------------------------------------
if scan_btn:
    with st.spinner(f"Scanning {selected_market}... this may take 30–60 seconds"):
        result_df = scrape_market(selected_market, past_days=past_days)

    if result_df.empty:
        st.sidebar.warning("No qualifying properties found. Try expanding filters or a different market.")
    else:
        st.sidebar.success(f"Found {len(result_df)} properties in {selected_market}")
        st.session_state["last_market"] = selected_market

# ---------------------------------------------------------------------------
# Active filters dict for DB query
# ---------------------------------------------------------------------------
active_filters = {
    "max_price": max_price,
    "min_beds": min_beds,
    "min_sqft": min_sqft,
    "min_ratio": min_ratio if min_ratio > 0 else None,
}

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_screener, tab_watchlist, tab_market = st.tabs(
    ["🔍 Screener", "📌 Watchlist", "📊 Market Analysis"]
)

# ===========================================================================
# TAB 1: SCREENER
# ===========================================================================
with tab_screener:
    st.markdown(f"### Real Estate Investment Screener")

    # Fetch properties from DB
    market_filter = selected_markets if selected_markets else None
    props_df = get_properties(market=market_filter, filters=active_filters)

    # Summary metrics
    if not props_df.empty:
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Properties", len(props_df))
        with col2:
            avg_price = props_df["price"].mean()
            st.metric("Avg Price", f"${avg_price:,.0f}")
        with col3:
            qualifying = props_df[props_df["rent_ratio"] >= 0.01]
            st.metric("≥1% Rule", len(qualifying))
        with col4:
            avg_ratio = props_df["rent_ratio"].mean() * 100
            st.metric("Avg Ratio", f"{avg_ratio:.2f}%")
        with col5:
            avg_score = props_df["score"].mean()
            st.metric("Avg Score", f"{avg_score:.0f}/100")

        st.markdown("---")

        # Prepare display table
        display_cols = {
            "score": "Score",
            "address": "Address",
            "city": "City",
            "state": "ST",
            "price": "Price",
            "beds": "Beds",
            "sqft": "Sqft",
            "est_rent": "Est. Rent",
            "rent_ratio": "Ratio",
            "days_on_market": "Days Listed",
        }

        available = [c for c in display_cols if c in props_df.columns]
        table_df = props_df[available].copy()
        table_df = table_df.rename(columns={c: display_cols[c] for c in available})

        # Format columns
        if "Price" in table_df.columns:
            table_df["Price"] = table_df["Price"].apply(lambda x: f"${x:,.0f}")
        if "Est. Rent" in table_df.columns:
            table_df["Est. Rent"] = table_df["Est. Rent"].apply(lambda x: f"${x:,.0f}/mo")
        if "Ratio" in table_df.columns:
            table_df["Ratio"] = table_df["Ratio"].apply(
                lambda x: f"{get_ratio_label(x)} {x*100:.2f}%"
            )
        if "Score" in table_df.columns:
            table_df["Score"] = table_df["Score"].apply(lambda x: f"{x:.0f}")
        if "Sqft" in table_df.columns:
            table_df["Sqft"] = table_df["Sqft"].apply(lambda x: f"{x:,.0f}")

        st.dataframe(
            table_df,
            use_container_width=True,
            height=420,
            hide_index=True,
        )

        # Property detail expanders
        st.markdown("#### Property Details")
        for _, row in props_df.head(20).iterrows():
            ratio = float(row.get("rent_ratio", 0))
            score = float(row.get("score", 0))
            badge_cls = "score-high" if score >= 70 else ("score-mid" if score >= 45 else "score-low")
            ratio_icon = get_ratio_label(ratio)

            label = (
                f"{ratio_icon} **{row.get('address', 'N/A')}**, {row.get('city', '')}, {row.get('state', '')}  "
                f"— ${float(row.get('price', 0)):,.0f} · {int(row.get('beds', 0))} bd · "
                f"{int(row.get('sqft', 0)):,} sqft · Score: {score:.0f}"
            )

            with st.expander(label):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"**Price:** ${float(row.get('price', 0)):,.0f}")
                    st.markdown(f"**Beds/Baths:** {row.get('beds', '?')} / {row.get('baths', '?')}")
                    st.markdown(f"**Sqft:** {int(row.get('sqft', 0)):,}")
                    st.markdown(f"**Year Built:** {row.get('year_built', 'N/A')}")
                with c2:
                    st.markdown(f"**Est. Rent (3BR FMR):** ${float(row.get('est_rent', 0)):,.0f}/mo")
                    st.markdown(f"**Rent Ratio:** {ratio_icon} {ratio*100:.2f}%")
                    st.markdown(f"**Investment Score:** {score:.0f} / 100")
                    st.markdown(f"**Days Listed:** {row.get('days_on_market', 'N/A')}")
                with c3:
                    st.markdown(f"**ZIP:** {row.get('zip_code', 'N/A')}")
                    st.markdown(f"**County:** {row.get('county', 'N/A')}")
                    hoa = float(row.get("hoa_fee", 0) or 0)
                    st.markdown(f"**HOA:** {'None' if hoa == 0 else f'${hoa:,.0f}/mo'}")
                    tax = float(row.get("tax_amount", 0) or 0)
                    st.markdown(f"**Annual Tax:** {'N/A' if tax == 0 else f'${tax:,.0f}'}")

                # Score breakdown
                breakdown_raw = row.get("score_breakdown", "{}")
                if isinstance(breakdown_raw, str):
                    try:
                        breakdown = json.loads(breakdown_raw)
                    except Exception:
                        breakdown = {}
                elif isinstance(breakdown_raw, dict):
                    breakdown = breakdown_raw
                else:
                    breakdown = {}

                if breakdown:
                    st.markdown("**Score Breakdown:**")
                    bc1, bc2, bc3, bc4, bc5 = st.columns(5)
                    bc1.metric("Rent Ratio", f"{breakdown.get('rent_ratio_score', 0):.0f}/40")
                    bc2.metric("Price", f"{breakdown.get('price_score', 0):.0f}/20")
                    bc3.metric("Size", f"{breakdown.get('size_score', 0):.0f}/20")
                    bc4.metric("Beds", f"{breakdown.get('bed_score', 0)}/10")
                    bc5.metric("Freshness", f"{breakdown.get('dom_score', 0)}/10")

                # Links + watchlist
                property_url = str(row.get("property_url", "") or row.get("url", "") or "")
                link_col, btn_col = st.columns([3, 1])
                with link_col:
                    if property_url and property_url.startswith("http"):
                        st.markdown(f"[🔗 View on Realtor.com]({property_url})")
                    else:
                        city_slug = str(row.get("city", "")).replace(" ", "-")
                        state_slug = str(row.get("state", ""))
                        fallback_url = f"https://www.realtor.com/realestateandhomes-search/{city_slug}_{state_slug}"
                        st.markdown(f"[🔗 Search Realtor.com]({fallback_url})")
                with btn_col:
                    if st.button("📌 Add to Watchlist", key=f"wl_{row.get('id', '')}_{row.get('mls_id', '')}"):
                        success = add_to_watchlist(row.to_dict())
                        if success:
                            st.success("Added to watchlist!")
                        else:
                            st.info("Already in watchlist or error.")
    else:
        if not selected_markets:
            st.info(
                "Select markets to display in **View Markets** (sidebar), "
                "then click **🔍 Scan Market** to fetch listings."
            )
        else:
            markets_str = ", ".join(selected_markets[:5])
            if len(selected_markets) > 5:
                markets_str += f" +{len(selected_markets) - 5} more"
            st.info(
                f"No properties found for **{markets_str}** with current filters.  \n"
                "Click **🔍 Scan Market** in the sidebar to fetch listings, or adjust your filters."
            )

        st.markdown("#### How to get started")
        st.markdown("""
        1. Select a market in the sidebar (e.g. *Little Rock, AR*)
        2. Click **🔍 Scan Market** — this pulls live listings from Realtor.com
        3. Properties are scored 0–100 based on the 1% rule, price, size, and freshness
        4. Add promising properties to your **Watchlist** to track them
        """)


# ===========================================================================
# TAB 2: WATCHLIST
# ===========================================================================
with tab_watchlist:
    st.markdown("### 📌 Watchlist")

    wl_df = get_watchlist()

    if wl_df.empty:
        st.info("Your watchlist is empty. Add properties from the Screener tab.")
    else:
        # Summary row
        wl_col1, wl_col2, wl_col3, wl_col4 = st.columns(4)
        with wl_col1:
            st.metric("Saved", len(wl_df))
        with wl_col2:
            researching = len(wl_df[wl_df["status"] == "Researching"])
            st.metric("Researching", researching)
        with wl_col3:
            offered = len(wl_df[wl_df["status"] == "Made Offer"])
            st.metric("Made Offer", offered)
        with wl_col4:
            under_contract = len(wl_df[wl_df["status"] == "Under Contract"])
            st.metric("Under Contract", under_contract)

        st.markdown("---")

        for _, row in wl_df.iterrows():
            item_id = int(row["id"])
            ratio = float(row.get("rent_ratio", 0) or 0)
            icon = get_ratio_label(ratio)
            score = float(row.get("score", 0) or 0)
            status = str(row.get("status", "Researching"))

            status_colors = {
                "Researching": "🔵",
                "Made Offer": "🟠",
                "Under Contract": "🟢",
                "Passed": "⚫",
            }
            status_icon = status_colors.get(status, "⚪")

            label = (
                f"{status_icon} {icon} **{row.get('address', 'N/A')}**, "
                f"{row.get('city', '')}, {row.get('state', '')} — "
                f"${float(row.get('price', 0)):,.0f} · Score: {score:.0f}"
            )

            with st.expander(label):
                wc1, wc2 = st.columns(2)
                with wc1:
                    st.markdown(f"**Price:** ${float(row.get('price', 0)):,.0f}")
                    st.markdown(f"**Beds:** {row.get('beds', '?')}")
                    st.markdown(f"**Sqft:** {int(row.get('sqft', 0) or 0):,}")
                    st.markdown(f"**Est. Rent:** ${float(row.get('est_rent', 0) or 0):,.0f}/mo")
                    st.markdown(f"**Rent Ratio:** {icon} {ratio*100:.2f}%")
                    property_url = str(row.get("property_url", "") or row.get("url", "") or "")
                    if property_url and property_url.startswith("http"):
                        st.markdown(f"[🔗 View on Realtor.com]({property_url})")
                    else:
                        city_slug = str(row.get("city", "")).replace(" ", "-")
                        state_slug = str(row.get("state", ""))
                        fallback_url = f"https://www.realtor.com/realestateandhomes-search/{city_slug}_{state_slug}"
                        st.markdown(f"[🔗 Search Realtor.com]({fallback_url})")
                with wc2:
                    new_status = st.selectbox(
                        "Status",
                        WATCHLIST_STATUSES,
                        index=WATCHLIST_STATUSES.index(status) if status in WATCHLIST_STATUSES else 0,
                        key=f"status_{item_id}",
                    )
                    new_notes = st.text_area(
                        "Notes",
                        value=str(row.get("notes", "") or ""),
                        key=f"notes_{item_id}",
                        height=100,
                        placeholder="Add notes about this property...",
                    )
                    save_col, del_col = st.columns(2)
                    with save_col:
                        if st.button("💾 Save", key=f"save_{item_id}"):
                            update_watchlist_item(item_id, new_notes, new_status)
                            st.success("Saved!")
                            st.rerun()
                    with del_col:
                        if st.button("🗑️ Remove", key=f"del_{item_id}"):
                            remove_from_watchlist(item_id)
                            st.rerun()

        # Export
        st.markdown("---")
        csv_data = wl_df.to_csv(index=False)
        st.download_button(
            "⬇️ Export Watchlist (CSV)",
            data=csv_data,
            file_name="watchlist.csv",
            mime="text/csv",
        )


# ===========================================================================
# TAB 3: MARKET ANALYSIS
# ===========================================================================
with tab_market:
    st.markdown("### 📊 Market Analysis")

    markets_df = get_markets()

    if markets_df.empty:
        st.info("No markets scanned yet. Use the Screener tab to scan markets.")
    else:
        # Summary table
        display_markets = markets_df.copy()
        if "avg_price" in display_markets.columns:
            display_markets["avg_price"] = display_markets["avg_price"].apply(
                lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A"
            )
        if "avg_rent_ratio" in display_markets.columns:
            display_markets["avg_rent_ratio"] = display_markets["avg_rent_ratio"].apply(
                lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A"
            )
        if "last_scraped" in display_markets.columns:
            display_markets["last_scraped"] = pd.to_datetime(
                display_markets["last_scraped"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M")

        rename_map = {
            "location": "Market",
            "last_scraped": "Last Scanned",
            "property_count": "Total Props",
            "avg_price": "Avg Price",
            "avg_rent_ratio": "Avg Ratio",
            "qualifying_count": "≥1% Rule",
        }
        avail = [c for c in rename_map if c in display_markets.columns]
        st.dataframe(
            display_markets[avail].rename(columns=rename_map),
            use_container_width=True,
            hide_index=True,
        )

        # Charts
        raw_markets = get_markets()
        if not raw_markets.empty and len(raw_markets) > 1:
            st.markdown("---")
            ch1, ch2 = st.columns(2)

            with ch1:
                st.markdown("##### Average Price by Market")
                fig_price = px.bar(
                    raw_markets,
                    x="location",
                    y="avg_price",
                    color="avg_price",
                    color_continuous_scale="Blues",
                    labels={"location": "Market", "avg_price": "Avg Price ($)"},
                    template="plotly_dark",
                )
                fig_price.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    coloraxis_showscale=False,
                    xaxis_tickangle=-30,
                    margin=dict(l=0, r=0, t=20, b=60),
                )
                fig_price.update_traces(marker_line_width=0)
                st.plotly_chart(fig_price, use_container_width=True)

            with ch2:
                st.markdown("##### Avg Rent Ratio by Market")
                raw_markets["ratio_pct"] = raw_markets["avg_rent_ratio"] * 100
                fig_ratio = px.bar(
                    raw_markets,
                    x="location",
                    y="ratio_pct",
                    color="ratio_pct",
                    color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"],
                    labels={"location": "Market", "ratio_pct": "Avg Rent Ratio (%)"},
                    template="plotly_dark",
                )
                fig_ratio.add_hline(
                    y=1.0,
                    line_dash="dash",
                    line_color="#22c55e",
                    annotation_text="1% target",
                    annotation_position="top right",
                )
                fig_ratio.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    coloraxis_showscale=False,
                    xaxis_tickangle=-30,
                    margin=dict(l=0, r=0, t=20, b=60),
                )
                fig_ratio.update_traces(marker_line_width=0)
                st.plotly_chart(fig_ratio, use_container_width=True)

            # Scatter: price vs ratio
            all_props = get_all_properties()
            if not all_props.empty and "price" in all_props.columns and "rent_ratio" in all_props.columns:
                st.markdown("##### Price vs. Rent Ratio (all markets)")
                scatter_df = all_props[all_props["price"] > 0].copy()
                scatter_df["ratio_pct"] = scatter_df["rent_ratio"] * 100
                scatter_df["address_short"] = scatter_df.get("address", pd.Series(dtype=str)).apply(
                    lambda x: str(x)[:30] if pd.notna(x) else ""
                )

                fig_scatter = px.scatter(
                    scatter_df,
                    x="price",
                    y="ratio_pct",
                    color="market",
                    size="score",
                    hover_data=["address_short", "beds", "sqft"],
                    labels={
                        "price": "List Price ($)",
                        "ratio_pct": "Rent Ratio (%)",
                        "market": "Market",
                        "score": "Score",
                    },
                    template="plotly_dark",
                )
                fig_scatter.add_hline(
                    y=1.0,
                    line_dash="dash",
                    line_color="#22c55e",
                    annotation_text="1% rule threshold",
                )
                fig_scatter.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0, r=0, t=20, b=40),
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

        # Per-market qualifying counts bar
        if not raw_markets.empty:
            st.markdown("##### Qualifying Properties (≥1% Rule) per Market")
            fig_qual = px.bar(
                raw_markets.sort_values("qualifying_count", ascending=True),
                x="qualifying_count",
                y="location",
                orientation="h",
                color="qualifying_count",
                color_continuous_scale="Greens",
                labels={"qualifying_count": "# Properties ≥1%", "location": "Market"},
                template="plotly_dark",
            )
            fig_qual.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                coloraxis_showscale=False,
                margin=dict(l=0, r=0, t=20, b=20),
                height=max(200, len(raw_markets) * 40),
            )
            fig_qual.update_traces(marker_line_width=0)
            st.plotly_chart(fig_qual, use_container_width=True)
