from pathlib import Path
import os
import platform

import pandas as pd
import streamlit as st

from collectors import get_collector, get_supported_exchange_names
from db import DB_PATH, connect, ensure_seed_data, get_fee_row, init_db, list_exchanges
from fees_service import (
    ServiceError,
    add_exchange_with_defaults,
    build_comparison_dataframe,
    delete_exchange_cascade,
    fetch_and_store_bitvavo_quote,
    save_exchange_fees,
)

# ✅ Alleen de 3 werkende exchanges tonen op Streamlit Cloud
LIVE_EXCHANGES = ("Bitvavo", "Kraken", "Coinbase")

st.set_page_config(
    page_title="KiralyAI | Crypto Exchange Cost Dashboard",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def apply_light_style() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #F9FAFB;
            color: #111827;
        }
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1.25rem;
        }
        h1, h2, h3, h4 {
            margin-top: 0.2rem;
            margin-bottom: 0.35rem;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(17, 24, 39, 0.04);
        }
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: 14px 18px;
        }
        [data-testid="stButton"] > button,
        [data-testid="stDownloadButton"] > button {
            background: #FFFFFF !important;
            color: #111827 !important;
            border: 1px solid #D1D5DB !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
        }
        [data-testid="stButton"] > button:hover,
        [data-testid="stDownloadButton"] > button:hover {
            background: #F3F4F6 !important;
            color: #111827 !important;
            border-color: #9CA3AF !important;
        }
        [data-testid="stButton"] > button:focus,
        [data-testid="stDownloadButton"] > button:focus {
            color: #111827 !important;
            border-color: #3B82F6 !important;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25) !important;
        }
        [data-testid="stButton"] > button:disabled,
        [data-testid="stDownloadButton"] > button:disabled {
            background: #F9FAFB !important;
            color: #9CA3AF !important;
            border-color: #E5E7EB !important;
            cursor: not-allowed !important;
        }
        [data-baseweb="input"] input,
        [data-baseweb="select"] input,
        [data-baseweb="select"] span,
        [data-baseweb="select"] div,
        [data-baseweb="textarea"] textarea {
            color: #111827 !important;
        }
        [data-baseweb="input"] input::placeholder,
        [data-baseweb="textarea"] textarea::placeholder {
            color: #6B7280 !important;
            opacity: 1 !important;
        }
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        [data-baseweb="textarea"] > div {
            background: #FFFFFF !important;
            border-color: #D1D5DB !important;
        }
        .kiraly-subtle {
            color: #6B7280;
            font-size: 0.95rem;
        }
        .header-subtitle {
            color: #6B7280;
            text-align: right;
            font-size: 0.9rem;
            margin-top: 2px;
        }
        .header-brand {
            display: flex;
            align-items: center;
            min-height: 96px;
        }
        .control-label {
            color: #374151;
            font-weight: 600;
            font-size: 0.82rem;
            margin-bottom: 4px;
        }
        div[data-testid="stDataFrame"] {
            background: #FFFFFF !important;
            border: 1px solid #E5E7EB;
            border-radius: 10px;
            overflow: hidden;
        }
        div[data-testid="stDataFrame"] [role="grid"] {
            background: #FFFFFF !important;
            color: #111827 !important;
        }

        /* ✅ VERBERG sidebar + hamburger (zodat klanten geen refresh/debug zien) */
        section[data-testid="stSidebar"] { display: none !important; }
        button[kind="header"] { display: none !important; }

        /* ✅ VERBERG Streamlit menu/footer */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }

        @media (max-width: 900px) {
            .block-container { padding-top: 0.5rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    with st.container():
        left_col, right_col = st.columns([5, 3], vertical_alignment="center")

        with left_col:
            logo_col, name_col = st.columns([1, 7], vertical_alignment="center")
            with logo_col:
                st.markdown('<div class="header-brand">', unsafe_allow_html=True)
                try:
                    st.image(str(Path("assets/kiraly-logo.png")), width=100)
                except Exception:
                    pass
                st.markdown("</div>", unsafe_allow_html=True)
            with name_col:
                st.markdown("### KiralyAI")

        with right_col:
            st.markdown(
                '<div class="header-subtitle">Crypto Exchange Cost Dashboard</div>',
                unsafe_allow_html=True,
            )

        st.divider()


def is_streamlit_cloud() -> bool:
    if os.getenv("STREAMLIT_CLOUD"):
        return True
    if "streamlit" in platform.node().lower():
        return True
    return False


def _is_admin_mode() -> bool:
    """
    Admin mode aanzetten via:
    - Streamlit Cloud secrets: ADMIN_MODE="true"
    OF
    - URL param: ?admin=1  (handig voor jezelf)
    """
    try:
        qp = st.query_params
        if str(qp.get("admin", "")).strip() in ("1", "true", "True", "yes"):
            return True
    except Exception:
        pass

    try:
        return str(st.secrets.get("ADMIN_MODE", "false")).lower() == "true"
    except Exception:
        return False


def _get_dashboard_exchanges(con) -> list[str]:
    supported = set(get_supported_exchange_names())
    allowed = set(LIVE_EXCHANGES)
    rows = list_exchanges(con)
    return [
        str(row["name"])
        for row in rows
        if str(row["name"]) in supported and str(row["name"]) in allowed
    ]


def _refresh_live_quotes(
    con, symbol: str, exchange_names: list[str]
) -> tuple[list[str], dict[str, str], list[str]]:
    successes: list[str] = []
    failures: dict[str, str] = {}
    fallback_used: list[str] = []

    for exchange_name in exchange_names:
        try:
            collector = get_collector(exchange_name)
            fetch_and_store_bitvavo_quote(
                con,
                symbol=symbol,
                collector=collector,
                exchange_name=exchange_name,
            )
            successes.append(exchange_name)

            if getattr(collector, "last_quote_mode", "") == "fallback_btcusdt_usdteur":
                fallback_used.append(exchange_name)
        except Exception as exc:
            failures[exchange_name] = str(exc)
            print(f"[live-refresh] {exchange_name}: {exc}")

    return successes, failures, fallback_used


def render_controls(con):
    with st.container(border=True):
        st.markdown("#### Market Controls")

        try:
            exchange_names_for_fetch = _get_dashboard_exchanges(con)
        except Exception as exc:
            exchange_names_for_fetch = []
            st.error(f"Could not load exchanges for fetch: {exc}")

        default_fetch_index = (
            exchange_names_for_fetch.index("Bitvavo")
            if "Bitvavo" in exchange_names_for_fetch
            else 0
        )

        c1, c2, c3, c4 = st.columns(4, gap="small", vertical_alignment="bottom")

        with c1:
            st.markdown('<div class="control-label">Pair</div>', unsafe_allow_html=True)
            symbol = st.selectbox("Pair", ["BTC-EUR"], label_visibility="collapsed")

        with c2:
            st.markdown('<div class="control-label">Amount</div>', unsafe_allow_html=True)
            amount = st.selectbox("Amount", [100, 1000, 10000], index=1, label_visibility="collapsed")

        with c3:
            st.markdown('<div class="control-label">Live Exchange</div>', unsafe_allow_html=True)
            if exchange_names_for_fetch:
                _ = st.selectbox(
                    "Live quote exchange",
                    exchange_names_for_fetch,
                    index=default_fetch_index,
                    label_visibility="collapsed",
                )
            else:
                st.info("No exchanges available.")

        with c4:
            st.markdown('<div class="control-label">Action</div>', unsafe_allow_html=True)
            fetch_clicked = st.button(
                "Fetch Live Quotes",
                disabled=not exchange_names_for_fetch,
                use_container_width=True,
            )

        if fetch_clicked:
            refreshed, failed, fallback_used = _refresh_live_quotes(
                con, symbol=symbol, exchange_names=exchange_names_for_fetch
            )
            st.session_state["fallback_exchanges"] = fallback_used

            if refreshed:
                st.success(f"Live quotes updated for: {', '.join(refreshed)}")

            # (Voor deze 3 exchanges verwacht je normaliter geen fallback,
            # maar we laten het netjes zien als het ooit gebeurt.)
            if fallback_used:
                st.info(f"Fallback used (USDT->EUR): {', '.join(fallback_used)}")

            if failed:
                # filter naar LIVE_EXCHANGES zodat je nooit “spook exchanges” ziet
                failed = {name: err for name, err in failed.items() if name in LIVE_EXCHANGES}
                if failed:
                    st.warning(
                        "Some exchanges failed: "
                        + "; ".join([f"{name}: {error}" for name, error in failed.items()])
                    )

    return symbol, amount


def render_admin(con) -> None:
    st.subheader("Admin: Fees aanpassen")

    with st.expander("Open fee editor", expanded=False):
        with st.container(border=True):
            st.markdown("#### Add exchange (admin)")
            with st.form("add_exchange_form", clear_on_submit=True):
                new_exchange_name = st.text_input("Name", key="new_exchange_name")
                new_exchange_type = st.selectbox("Type", ["exchange", "broker"], key="new_exchange_type")
                new_exchange_website = st.text_input("Website", key="new_exchange_website")
                add_exchange_submitted = st.form_submit_button("Add exchange")

            if add_exchange_submitted:
                try:
                    add_exchange_with_defaults(
                        con,
                        name=new_exchange_name,
                        exchange_type=new_exchange_type,
                        website=new_exchange_website,
                    )
                    st.success(f"Added exchange: {new_exchange_name.strip()}")
                    st.rerun()
                except ServiceError as exc:
                    st.error(str(exc))

            try:
                exchanges = list_exchanges(con)
            except Exception as exc:
                exchanges = []
                st.error(f"Could not load exchanges: {exc}")

            if not exchanges:
                st.info("No exchanges found. Add one above.")
                return

            ex_name_to_id = {str(ex["name"]): int(ex["id"]) for ex in exchanges}
            selected_name = st.selectbox("Exchange", list(ex_name_to_id.keys()))
            selected_id = ex_name_to_id[selected_name]

            fee_row = get_fee_row(con, selected_id)
            if fee_row:
                trading_fee_pct = float(fee_row["trading_fee_pct"])
                deposit_ideal_fee_eur = float(fee_row["deposit_ideal_fee_eur"])
                withdraw_eur_fee_eur = float(fee_row["withdraw_eur_fee_eur"])
                spread_estimate_pct = float(fee_row["spread_estimate_pct"])
                source_url = str(fee_row["source_url"] or "")
            else:
                trading_fee_pct = 0.0
                deposit_ideal_fee_eur = 0.0
                withdraw_eur_fee_eur = 0.0
                spread_estimate_pct = 0.0
                source_url = ""

            col_a, col_b = st.columns(2)
            with col_a:
                new_trading_fee = st.number_input(
                    "Trading fee %",
                    value=trading_fee_pct,
                    step=0.01,
                    format="%.4f",
                    help="Gebruik hier je default (taker/instant) fee percentage.",
                )
                new_spread_est = st.number_input(
                    "Spread estimate %",
                    value=spread_estimate_pct,
                    step=0.01,
                    format="%.4f",
                    help="Fallback spread als er geen live orderbook quote is.",
                )
            with col_b:
                new_ideal_fee = st.number_input(
                    "iDEAL deposit fee (€)",
                    value=deposit_ideal_fee_eur,
                    step=0.10,
                    format="%.2f",
                )
                new_withdraw_fee = st.number_input(
                    "EUR withdrawal fee (€)",
                    value=withdraw_eur_fee_eur,
                    step=0.10,
                    format="%.2f",
                )

            new_source = st.text_input("Source URL", value=source_url)

            if st.button("Save fees"):
                try:
                    save_exchange_fees(
                        con,
                        exchange_id=selected_id,
                        trading_fee_pct=float(new_trading_fee),
                        deposit_ideal_fee_eur=float(new_ideal_fee),
                        withdraw_eur_fee_eur=float(new_withdraw_fee),
                        spread_estimate_pct=float(new_spread_est),
                        source_url=new_source,
                    )
                    st.success(f"Saved fees for {selected_name}")
                except ServiceError as exc:
                    st.error(str(exc))

            st.markdown("#### Delete exchange")
            st.markdown(
                '<div class="kiraly-subtle">Only remove exchanges you no longer want to compare.</div>',
                unsafe_allow_html=True,
            )
            with st.form("delete_exchange_form"):
                delete_exchange_name = st.selectbox(
                    "Exchange to delete",
                    list(ex_name_to_id.keys()),
                    key="delete_exchange_name",
                )
                confirm_delete = st.checkbox(
                    "I understand this will delete related fees and quotes.",
                    key="confirm_delete_exchange",
                )
                delete_exchange_submitted = st.form_submit_button("Delete exchange")

            if delete_exchange_submitted:
                if not confirm_delete:
                    st.warning("Please confirm delete before continuing.")
                else:
                    try:
                        delete_exchange_cascade(con, ex_name_to_id[delete_exchange_name])
                        st.success(f"Deleted exchange: {delete_exchange_name}")
                        st.rerun()
                    except ServiceError as exc:
                        st.error(str(exc))


def _format_pct(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".") + "%"


def _resolve_total_column(df: pd.DataFrame, amount: int) -> str:
    expected = f"Total € (op €{amount})"
    if expected in df.columns:
        return expected

    prefix_matches = [col for col in df.columns if str(col).startswith("Total € (op €")]
    if prefix_matches:
        return prefix_matches[0]

    generic_matches = [col for col in df.columns if str(col).startswith("Total €")]
    if generic_matches:
        return generic_matches[0]

    raise KeyError(f"No total-eur column found in dataframe columns: {list(df.columns)}")


def render_table(df: pd.DataFrame, symbol: str, amount: int) -> None:
    with st.container(border=True):
        st.subheader("Vergelijking")

        if df.empty:
            st.info("No comparison data available.")
            st.download_button(
                "Export CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=f"crypto_fee_comparison_{symbol}_{amount}.csv",
                mime="text/csv",
                disabled=True,
            )
            return

        total_col = _resolve_total_column(df, amount)
        df_display = df.copy()
        df_display.insert(0, "Status", "")

        cheapest_idx = df_display[total_col].idxmin()
        df_display.loc[cheapest_idx, "Status"] = "Cheapest"

        for col in ["Fee %", "Spread %", "Total %"]:
            if col in df_display.columns:
                df_display[col] = df_display[col].map(_format_pct)

        for col in [total_col, "iDEAL fee €", "EUR opname €"]:
            if col in df_display.columns:
                df_display[col] = df_display[col].map(lambda v: f"€ {float(v):.2f}")

        st.dataframe(df_display, width="stretch")
        st.download_button(
            "Export CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"crypto_fee_comparison_{symbol}_{amount}.csv",
            mime="text/csv",
        )


def render_debug(con, symbol: str) -> None:
    # Debug alleen in admin mode, dus klanten zien dit nooit
    st.subheader("Debug")
    st.write("DB:", str(DB_PATH))
    st.write("Streamlit Cloud mode:", is_streamlit_cloud())
    st.write("Live exchanges:", list(LIVE_EXCHANGES))

    exchanges = list_exchanges(con)
    exchange_names = [str(row["name"]) for row in exchanges]
    st.write("Exchanges:", exchange_names)

    cur = con.cursor()
    cur.execute(
        """
        SELECT e.name AS exchange,
               COUNT(q.rowid) AS quote_count,
               MAX(q.ts) AS latest_ts
        FROM exchanges e
        LEFT JOIN quotes q
               ON q.exchange_id = e.id
              AND q.symbol = ?
        GROUP BY e.id, e.name
        ORDER BY e.name
        """,
        (symbol,),
    )
    rows = cur.fetchall()
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Exchange": str(row["exchange"]),
                    "Quote count": int(row["quote_count"]),
                    "Latest ts": row["latest_ts"],
                }
                for row in rows
            ]
        ),
        width="stretch",
    )


# -------------------------
# App start
# -------------------------
apply_light_style()
render_header()

ADMIN_MODE = _is_admin_mode()

init_db()
con = connect()
ensure_seed_data(con)

symbol, amount = render_controls(con)

dashboard_exchanges = _get_dashboard_exchanges(con)

# Let op: we refreshen niet automatisch (geen sidebar/timer); user klikt op Fetch Live Quotes.
# Maar we proberen wél bij eerste load alvast live data te hebben:
_, refresh_failures, fallback_used = _refresh_live_quotes(con, symbol=symbol, exchange_names=dashboard_exchanges)

if "fallback_exchanges" not in st.session_state:
    st.session_state["fallback_exchanges"] = []

if fallback_used:
    st.session_state["fallback_exchanges"] = fallback_used

if refresh_failures:
    # filter strikt naar LIVE_EXCHANGES
    refresh_failures = {name: err for name, err in refresh_failures.items() if name in LIVE_EXCHANGES}
    if refresh_failures and ADMIN_MODE:
        # Alleen admin ziet dit soort waarschuwingen.
        st.warning(
            "Live quote refresh issues: "
            + "; ".join([f"{name}: {error}" for name, error in refresh_failures.items()])
        )

try:
    df = build_comparison_dataframe(con, symbol=symbol, amount=float(amount))
except ServiceError as exc:
    st.error(str(exc))
    df = pd.DataFrame()
except Exception as exc:
    st.error(f"Unexpected error while building dashboard: {exc}")
    df = pd.DataFrame()

# ✅ Filter altijd naar alleen de 3 live exchanges
if not df.empty:
    df = df[df["Exchange"].isin(dashboard_exchanges)].copy()

    # Als je echt alleen live wil: laat live rows staan (fallback eruit)
    if "Spread source" in df.columns:
        # we laten live + fallback toe, maar je kunt fallback ook eruit filteren als je wil.
        # Voor nu: live en fallback toegestaan, maar fallback label netjes maken.
        fallback_set = set(st.session_state.get("fallback_exchanges", []))
        if fallback_set:
            df.loc[df["Exchange"].isin(fallback_set), "Spread source"] = "fallback (BTCUSDT * USDT->EUR)"

render_table(df, symbol=symbol, amount=int(amount))

# ✅ Debug + Admin alleen voor jou (admin mode)
if ADMIN_MODE:
    st.divider()
    render_debug(con, symbol=symbol)
    st.divider()
    render_admin(con)

st.caption(
    "Tip: vul echte fees + source links in via de Admin editor. Bitvavo/Kraken/Coinbase spread is live als je een quote fetch doet."
    if ADMIN_MODE
    else ""
)

con.close()