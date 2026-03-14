from typing import Dict, List

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from database import add_trade, close_trade, get_all_trades, init_db

st.set_page_config(
    page_title="Binance Futures PnL Tracker",
    page_icon="📈",
    layout="wide",
)

init_db()

BINANCE_FUTURES_EXCHANGE_INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"
BINANCE_FUTURES_MARK_PRICES = "https://fapi.binance.com/fapi/v1/premiumIndex"

LOGIN_USERNAME = "rahim"
LOGIN_PASSWORD = "rahim123"

REQUEST_TIMEOUT = 20
AUTO_REFRESH_MS = 3000  # 3 seconds; safer for Streamlit Cloud than 2 seconds


def get_http_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 BinanceFuturesPnLTracker/1.0",
            "Accept": "application/json",
        }
    )
    return session


def inject_css() -> None:
    st.markdown(
        """
        <style>
            .main > div {
                padding-top: 1.2rem;
            }
            .block-container {
                padding-top: 1.2rem;
                padding-bottom: 2rem;
            }
            .app-card {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 18px;
                padding: 1.15rem 1.15rem 1rem 1.15rem;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
                margin-bottom: 1rem;
            }
            .big-title {
                font-size: 2rem;
                font-weight: 800;
                margin-bottom: 0.25rem;
                color: #0f172a;
            }
            .muted {
                color: #6b7280;
                font-size: 0.97rem;
            }
            .metric-box {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 1rem;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
                min-height: 108px;
            }
            .trade-pill {
                display: inline-block;
                padding: 0.25rem 0.65rem;
                border-radius: 999px;
                font-size: 0.8rem;
                font-weight: 700;
                margin-right: 0.45rem;
                margin-bottom: 0.5rem;
            }
            .long-pill {
                background: rgba(34, 197, 94, 0.12);
                color: #15803d;
            }
            .short-pill {
                background: rgba(239, 68, 68, 0.12);
                color: #b91c1c;
            }
            .open-pill {
                background: rgba(59, 130, 246, 0.12);
                color: #1d4ed8;
            }
            .closed-pill {
                background: rgba(107, 114, 128, 0.12);
                color: #374151;
            }
            .pnl-profit {
                color: #15803d;
                font-weight: 800;
            }
            .pnl-loss {
                color: #b91c1c;
                font-weight: 800;
            }
            .small-label {
                color: #6b7280;
                font-size: 0.84rem;
            }
            .trade-card {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 18px;
                padding: 1rem;
                margin-bottom: 0.9rem;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
            }
            div[data-testid="stMetric"] {
                background: #ffffff;
                border-radius: 12px;
                padding: 0.1rem 0.1rem 0.1rem 0;
            }
            div[data-testid="stForm"] {
                border: none !important;
                padding: 0 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=21600, show_spinner=False)  # 6 hours
def fetch_symbols() -> List[str]:
    session = get_http_session()
    response = session.get(BINANCE_FUTURES_EXCHANGE_INFO, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    symbols: List[str] = []
    for item in payload.get("symbols", []):
        if (
            item.get("contractType") == "PERPETUAL"
            and item.get("status") == "TRADING"
            and item.get("symbol", "").endswith("USDT")
        ):
            symbols.append(item["symbol"])

    return sorted(symbols)


@st.cache_data(ttl=2, show_spinner=False)
def fetch_mark_prices() -> Dict[str, float]:
    session = get_http_session()
    response = session.get(BINANCE_FUTURES_MARK_PRICES, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()

    prices: Dict[str, float] = {}
    if isinstance(payload, list):
        for item in payload:
            symbol = item.get("symbol")
            try:
                prices[symbol] = float(item.get("markPrice", 0))
            except (TypeError, ValueError):
                continue

    return prices


def format_money(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    if abs(value) >= 1:
        return f"{value:,.4f}"
    return f"{value:,.8f}"


def pnl_for_trade(side: str, quantity: float, entry_price: float, current_price: float) -> float:
    if side == "LONG":
        return (current_price - entry_price) * quantity
    return (entry_price - current_price) * quantity


def pnl_class(value: float) -> str:
    return "pnl-profit" if value >= 0 else "pnl-loss"


def show_login() -> None:
    left, center, right = st.columns([1, 1.1, 1])

    with center:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("<div class='big-title'>Binance Futures PnL Tracker</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='muted'>Login with your requested demo credentials.</div>",
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="rahim")
            password = st.text_input("Password", type="password", placeholder="rahim123")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
                st.session_state["logged_in"] = True
                st.session_state["page"] = "dashboard"
                st.success("Login successful.")
                st.rerun()
            else:
                st.error("Invalid username or password.")

        st.markdown("</div>", unsafe_allow_html=True)


def top_bar() -> None:
    col1, col2, col3 = st.columns([4, 1.2, 1])

    with col1:
        st.markdown("<div class='big-title'>Binance Futures Portfolio Tracker</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='muted'>Live Binance mark-price based PnL with a simple clean trade journal.</div>",
            unsafe_allow_html=True,
        )

    with col2:
        if st.button("Open Trade History", use_container_width=True):
            st.session_state["page"] = "history"
            st.rerun()

    with col3:
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()


def render_trade_form(symbols: List[str], prices: Dict[str, float]) -> None:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.subheader("Add New Trade")

    search_text = st.text_input(
        "Search Binance Futures Symbol",
        placeholder="Type BTC, ETH, SOL, XRP...",
    ).strip().upper()

    filtered_symbols = [s for s in symbols if search_text in s] if search_text else symbols
    if not filtered_symbols:
        st.warning("No matching symbol found. Showing full symbol list.")
        filtered_symbols = symbols

    default_symbol = filtered_symbols[0]
    default_price = float(prices.get(default_symbol, 100.0))

    with st.form("new_trade_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2.3, 1.1, 1.15, 1.4])

        with c1:
            symbol = st.selectbox("Symbol", options=filtered_symbols, index=0)

        with c2:
            side = st.selectbox("Side", options=["LONG", "SHORT"], index=0)

        with c3:
            quantity = st.number_input(
                "Quantity",
                min_value=0.00000001,
                value=0.001,
                format="%.8f",
            )

        with c4:
            entry_price = st.number_input(
                "Entry Price",
                min_value=0.00000001,
                value=default_price,
                format="%.8f",
            )

        submitted = st.form_submit_button("Add Trade", use_container_width=True)

    if submitted:
        add_trade(
            symbol=symbol,
            side=side,
            quantity=float(quantity),
            entry_price=float(entry_price),
        )
        st.success(f"{side} trade added for {symbol}.")
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def summarize_open_trades(trades: List[dict], prices: Dict[str, float]) -> None:
    open_trades = [t for t in trades if t["status"] == "OPEN"]

    open_count = len(open_trades)
    total_unrealized = 0.0
    exposure = 0.0
    win_count = 0

    for trade in open_trades:
        current_price = prices.get(trade["symbol"])
        if current_price is None:
            continue

        quantity = float(trade["quantity"])
        entry_price = float(trade["entry_price"])

        pnl = pnl_for_trade(trade["side"], quantity, entry_price, current_price)
        total_unrealized += pnl
        exposure += quantity * entry_price

        if pnl > 0:
            win_count += 1

    cols = st.columns(4)
    metric_values = [
        ("Open Trades", str(open_count)),
        ("Unrealized PnL", format_money(total_unrealized)),
        ("Entry Exposure", format_money(exposure)),
        ("Trades in Profit", str(win_count)),
    ]

    for col, (label, value) in zip(cols, metric_values):
        with col:
            st.markdown("<div class='metric-box'>", unsafe_allow_html=True)
            st.markdown(f"<div class='small-label'>{label}</div>", unsafe_allow_html=True)

            if label == "Unrealized PnL":
                st.markdown(
                    f"<div class='{pnl_class(total_unrealized)}' style='font-size:1.6rem; margin-top:0.45rem;'>{value}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='font-size:1.6rem; font-weight:800; margin-top:0.45rem;'>{value}</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("</div>", unsafe_allow_html=True)


def render_trade_card(trade: dict, prices: Dict[str, float], allow_close: bool) -> None:
    symbol = trade["symbol"]
    side = trade["side"]
    quantity = float(trade["quantity"])
    entry_price = float(trade["entry_price"])
    status = trade["status"]

    st.markdown("<div class='trade-card'>", unsafe_allow_html=True)

    pill_side_class = "long-pill" if side == "LONG" else "short-pill"
    pill_status_class = "open-pill" if status == "OPEN" else "closed-pill"

    st.markdown(
        f"<span class='trade-pill {pill_side_class}'>{side}</span>"
        f"<span class='trade-pill {pill_status_class}'>{status}</span>"
        f"<span style='font-weight:800; font-size:1.1rem;'>{symbol}</span>",
        unsafe_allow_html=True,
    )

    cols = st.columns([1.1, 1.1, 1.1, 1.2, 1.4])
    cols[0].metric("Quantity", format_money(quantity))
    cols[1].metric("Entry Price", format_money(entry_price))

    if status == "OPEN":
        current_price = prices.get(symbol)
        current_display = "N/A" if current_price is None else format_money(current_price)
        pnl_value = 0.0 if current_price is None else pnl_for_trade(side, quantity, entry_price, current_price)

        cols[2].metric("Current Price", current_display)
        cols[3].markdown(
            f"<div class='small-label'>Live PnL</div>"
            f"<div class='{pnl_class(pnl_value)}' style='font-size:1.45rem; margin-top:0.35rem;'>{format_money(pnl_value)}</div>",
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            f"<div class='small-label'>Opened</div>"
            f"<div style='font-weight:600; margin-top:0.35rem;'>{trade['created_at']}</div>",
            unsafe_allow_html=True,
        )

        if allow_close:
            with st.expander(f"Close trade #{trade['id']}"):
                suggested_close = float(current_price if current_price is not None else entry_price)

                with st.form(f"close_form_{trade['id']}"):
                    close_price = st.number_input(
                        "Close Price",
                        min_value=0.00000001,
                        value=suggested_close,
                        format="%.8f",
                        key=f"close_price_{trade['id']}",
                    )
                    submitted = st.form_submit_button("Confirm Close", use_container_width=True)

                if submitted:
                    close_trade(int(trade["id"]), float(close_price))
                    st.success(f"Trade #{trade['id']} closed.")
                    st.rerun()

    else:
        close_price = float(trade["close_price"] or 0)
        realized_pnl = float(trade["realized_pnl"] or 0)

        cols[2].metric("Close Price", format_money(close_price))
        cols[3].markdown(
            f"<div class='small-label'>Final PnL</div>"
            f"<div class='{pnl_class(realized_pnl)}' style='font-size:1.45rem; margin-top:0.35rem;'>{format_money(realized_pnl)}</div>",
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            f"<div class='small-label'>Closed</div>"
            f"<div style='font-weight:600; margin-top:0.35rem;'>{trade['closed_at'] or '-'}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def dashboard_page(symbols: List[str], prices: Dict[str, float]) -> None:
    st_autorefresh(interval=AUTO_REFRESH_MS, key="dashboard_refresh")

    top_bar()
    render_trade_form(symbols, prices)

    trades = get_all_trades()
    summarize_open_trades(trades, prices)

    st.markdown("### Ongoing Trades")
    open_trades = [t for t in trades if t["status"] == "OPEN"]

    if not open_trades:
        st.info("No open trades yet.")
        return

    for trade in open_trades:
        render_trade_card(trade, prices, allow_close=True)


def history_page(prices: Dict[str, float]) -> None:
    st_autorefresh(interval=AUTO_REFRESH_MS, key="history_refresh")

    head1, head2 = st.columns([4, 1.2])

    with head1:
        st.markdown("<div class='big-title'>Trade History</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='muted'>Open trades stay at the top. Closed trades stay below them.</div>",
            unsafe_allow_html=True,
        )

    with head2:
        if st.button("Back to Dashboard", use_container_width=True):
            st.session_state["page"] = "dashboard"
            st.rerun()

    trades = get_all_trades()

    if not trades:
        st.info("No trades found.")
        return

    open_trades = [t for t in trades if t["status"] == "OPEN"]
    closed_trades = [t for t in trades if t["status"] == "CLOSED"]

    st.markdown("### Open Trades")
    if open_trades:
        for trade in open_trades:
            render_trade_card(trade, prices, allow_close=True)
    else:
        st.info("No open trades.")

    st.markdown("### Closed Trades")
    if closed_trades:
        for trade in closed_trades:
            render_trade_card(trade, prices, allow_close=False)
    else:
        st.info("No closed trades yet.")

    export_rows = []
    for trade in trades:
        export_rows.append(
            {
                "ID": trade["id"],
                "Symbol": trade["symbol"],
                "Side": trade["side"],
                "Quantity": trade["quantity"],
                "Entry Price": trade["entry_price"],
                "Status": trade["status"],
                "Close Price": trade["close_price"],
                "Final PnL": trade["realized_pnl"],
                "Created At": trade["created_at"],
                "Closed At": trade["closed_at"],
            }
        )

    df = pd.DataFrame(export_rows)

    st.download_button(
        "Download Trades CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="trade_history.csv",
        mime="text/csv",
        use_container_width=True,
    )


def main() -> None:
    inject_css()

    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("page", "dashboard")

    if not st.session_state["logged_in"]:
        show_login()
        return

    try:
        symbols = fetch_symbols()
        prices = fetch_mark_prices()

        if not symbols:
            raise requests.RequestException("No Binance Futures symbols were returned.")

    except requests.RequestException as exc:
        st.error(f"Could not load Binance Futures data right now: {exc}")
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        prices = {}

    if st.session_state["page"] == "history":
        history_page(prices)
    else:
        dashboard_page(symbols, prices)


if __name__ == "__main__":
    main()
