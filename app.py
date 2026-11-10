import smtplib
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots
from supabase import Client, create_client

st.set_page_config(page_title="PSX Quantum Terminal", layout="wide", page_icon="🚀")


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
@st.cache_resource
def get_admin_client() -> Client | None:
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])
    except Exception:
        return None


def get_client() -> Client | None:
    """Per-run client. Logged-in user's token is attached so RLS works."""
    try:
        client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        token = st.session_state.get("token")
        if token:
            client.postgrest.auth(token)
        return client
    except Exception:
        return None


for key, default in {"user": None, "token": None, "page": "user",
                     "edit_id": None, "alert": None}.items():
    if key not in st.session_state:
        st.session_state[key] = default

supabase = get_client()
supabase_admin = get_admin_client()
if supabase is None:
    st.error("Supabase Secrets Error: SUPABASE_URL / SUPABASE_KEY check karein.")
    st.stop()

st.markdown(
    """
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4253; }
    .admin-box { background-color: #2d1b4e; padding: 20px; border-radius: 15px; border: 2px solid #8a2be2; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def auth_page():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 PSX Quantum Access")
        mode = st.radio("Option", ["Login", "Sign Up"], horizontal=True)
        email = st.text_input("Email").strip()
        password = st.text_input("Password", type="password")

        if mode == "Login":
            if st.button("Login", use_container_width=True):
                if not email or not password:
                    st.warning("Email aur password dono likhein.")
                    return
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state["user"] = res.user
                    st.session_state["token"] = res.session.access_token if res.session else None
                    st.rerun()
                except Exception as e:
                    st.error(f"Login Error: {e}")
        else:
            if st.button("Create Account", use_container_width=True):
                if not email or len(password) < 6:
                    st.warning("Email likhein aur password kam az kam 6 characters ka rakhein.")
                    return
                try:
                    supabase.auth.sign_up({"email": email, "password": password})
                    st.success("Account created! Agar email confirmation on hai to email check karein, phir Login karein.")
                except Exception as e:
                    st.error(f"Sign Up Error: {e}")


if st.session_state["user"] is None:
    auth_page()
    st.stop()

user = st.session_state["user"]
admin_email = str(st.secrets.get("ADMIN_EMAIL", "")).strip().lower()
is_admin = bool(admin_email) and (user.email or "").lower() == admin_email

st.sidebar.header(f"👋 {user.email}")
st.sidebar.markdown("---")

if is_admin:
    st.sidebar.success("👑 Admin Access")
    if st.sidebar.button("🛡️ Admin Dashboard"):
        st.session_state["page"] = "admin"
else:
    st.sidebar.info("👤 User Mode")

if st.sidebar.button("📊 Stock Analyzer"):
    st.session_state["page"] = "user"
    st.session_state["edit_id"] = None
if st.sidebar.button("💼 My Portfolio"):
    st.session_state["page"] = "portfolio"
if st.sidebar.button("Logout"):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for k in ("user", "token", "edit_id", "alert"):
        st.session_state[k] = None
    st.session_state["page"] = "user"
    st.rerun()


# ---------------------------------------------------------------------------
# Data helpers (cached so Yahoo is not hit on every click)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_history(symbol: str, start=None, end=None, period=None) -> pd.DataFrame:
    ticker = yf.Ticker(symbol + ".KA")
    if period:
        return ticker.history(period=period)
    return ticker.history(start=start, end=end)


@st.cache_data(ttl=3600, show_spinner=False)
def get_info(symbol: str) -> dict:
    try:
        return yf.Ticker(symbol + ".KA").info or {}
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def get_dividends(symbol: str) -> pd.Series:
    try:
        return yf.Ticker(symbol + ".KA").dividends
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=900, show_spinner=False)
def get_news(symbol: str) -> list:
    try:
        return yf.Ticker(symbol + ".KA").news or []
    except Exception:
        return []


def calculate_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi[loss == 0] = 100
    return rsi


def trend_signal(price, sma20, sma50):
    if pd.isna(sma20) or pd.isna(sma50):
        return "⚪ Not enough data", "gray"
    if price > sma20 > sma50:
        return "🟢 Buy More", "green"
    if price < sma20 < sma50:
        return "🔴 Sell / Exit", "red"
    return "🟡 Hold", "yellow"


def trailing_dividend_yield(symbol: str, price: float) -> float:
    """Dividends of last 12 months / price, in percent."""
    divs = get_dividends(symbol)
    if divs is None or divs.empty or not price:
        return 0.0
    idx = divs.index.tz_localize(None) if divs.index.tz is not None else divs.index
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=365)
    total = divs[idx >= cutoff].sum()
    return float(total) / float(price) * 100


def send_email(target_price, current_price, symbol):
    try:
        sender = st.secrets["SENDER_EMAIL"]
        pwd = st.secrets["APP_PASSWORD"]
        msg = MIMEText(f"Alert! {symbol} is near target {target_price}. Current: {current_price}")
        msg["Subject"] = f"PSX Alert: {symbol}"
        msg["From"] = sender
        msg["To"] = user.email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(sender, pwd)
            server.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def show_admin_page():
    if not is_admin:
        st.error("Access denied.")
        return
    st.markdown('<div class="admin-box">', unsafe_allow_html=True)
    st.title("🛡️ Admin Control Center")
    if supabase_admin is None:
        st.error("SUPABASE_SERVICE_KEY missing hai.")
    else:
        try:
            users = supabase_admin.auth.admin.list_users()
            st.metric("Total Users", len(users))
            st.table(pd.DataFrame({"User Email": [u.email for u in users]}))
        except Exception as e:
            st.error(f"Error: {e}")
    st.markdown("</div>", unsafe_allow_html=True)


def show_portfolio_page():
    st.title("💼 Intelligent Portfolio")
    uid = user.id

    # ---- Edit mode ----
    if st.session_state["edit_id"] is not None:
        st.subheader("✏️ Edit Stock")
        try:
            res = (supabase.table("portfolios").select("*")
                   .eq("id", st.session_state["edit_id"]).eq("user_id", uid).single().execute())
            item = res.data
            c1, c2, c3, c4 = st.columns(4)
            e_symbol = c1.text_input("Symbol", value=item["symbol"]).strip().upper()
            e_qty = c2.number_input("Quantity", value=int(item["quantity"]), min_value=1)
            e_price = c3.number_input("Buy Price", value=float(item["buy_price"]), min_value=0.1)
            e_shariah = c4.selectbox("Shariah", ["Compliant", "Non-Compliant"],
                                     index=0 if item.get("shariah") == "Compliant" else 1)
            b1, b2 = st.columns(2)
            if b1.button("Update", use_container_width=True):
                (supabase.table("portfolios")
                 .update({"symbol": e_symbol, "quantity": e_qty, "buy_price": e_price, "shariah": e_shariah})
                 .eq("id", st.session_state["edit_id"]).eq("user_id", uid).execute())
                st.session_state["edit_id"] = None
                st.rerun()
            if b2.button("Cancel", use_container_width=True):
                st.session_state["edit_id"] = None
                st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
            st.session_state["edit_id"] = None
        return

    # ---- Add form ----
    with st.expander("➕ Add Stock"):
        with st.form("add_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            p_symbol = c1.text_input("Symbol").strip().upper()
            p_qty = c2.number_input("Quantity", min_value=1, step=1)
            p_price = c3.number_input("Buy Price", min_value=0.1)
            p_shariah = c4.selectbox("Shariah Status", ["Compliant", "Non-Compliant"])
            if st.form_submit_button("Save"):
                if not p_symbol:
                    st.warning("Symbol likhein.")
                elif get_history(p_symbol, period="5d").empty:
                    st.error(f"'{p_symbol}' PSX par nahi mila. Symbol check karein.")
                else:
                    try:
                        supabase.table("portfolios").insert({
                            "user_id": uid, "symbol": p_symbol, "quantity": int(p_qty),
                            "buy_price": float(p_price), "shariah": p_shariah,
                        }).execute()
                        st.success("Saved!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # ---- Portfolio list ----
    try:
        res = supabase.table("portfolios").select("*").eq("user_id", uid).execute()
    except Exception as e:
        st.error(f"Error: {e}  (agar token expire hua ho to Logout karke dobara Login karein)")
        return

    if not res.data:
        st.write("Portfolio is empty.")
        return

    total_inv, total_cur = 0.0, 0.0
    failed = []
    st.subheader("Analysis")
    for item in res.data:
        sym = item["symbol"]
        try:
            df = get_history(sym, period="1y")
            if df.empty:
                failed.append(sym)
                continue
            curr_p = float(df["Close"].iloc[-1])
            b_p, q = float(item["buy_price"]), int(item["quantity"])
            pl = (curr_p - b_p) * q
            sma20 = df["Close"].rolling(20).mean().iloc[-1]
            sma50 = df["Close"].rolling(50).mean().iloc[-1]
            advice, color = trend_signal(curr_p, sma20, sma50)
            div_y = trailing_dividend_yield(sym, curr_p)
            total_inv += b_p * q
            total_cur += curr_p * q

            c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1.5, 1.5, 1, 1])
            c1.write(f"**{sym}**")
            sh_c = "green" if item.get("shariah") == "Compliant" else "red"
            c2.markdown(f"<span style='color:{sh_c}; font-size:12px;'>● {item.get('shariah', 'Unknown')}</span>",
                        unsafe_allow_html=True)
            c3.write(f"P&L: {'📈' if pl > 0 else '📉'} Rs. {pl:,.2f}")
            c4.markdown(f"<span style='color:{color}; font-weight:bold;'>{advice}</span>", unsafe_allow_html=True)
            c5.write(f"Div: {div_y:.1f}%")
            if c6.button("🗑️", key=f"dl_{item['id']}"):
                supabase.table("portfolios").delete().eq("id", item["id"]).eq("user_id", uid).execute()
                st.rerun()
            with st.expander("Details"):
                st.write(f"Buy: {b_p} | Current: {curr_p:.2f} | Qty: {q}")
                if st.button("Edit", key=f"ed_{item['id']}"):
                    st.session_state["edit_id"] = item["id"]
                    st.rerun()
            st.markdown("---")
        except Exception:
            failed.append(sym)

    if failed:
        st.warning("In symbols ka data nahi aa saka: " + ", ".join(failed))

    c_inv, c_cur, c_net = st.columns(3)
    c_inv.metric("Total Invested", f"Rs. {total_inv:,.2f}")
    c_cur.metric("Current Value", f"Rs. {total_cur:,.2f}")
    net_pl = total_cur - total_inv
    c_net.metric("Net P&L", f"Rs. {net_pl:,.2f}", delta=f"{net_pl:,.2f}")


def show_analyzer_page():
    st.title("🚀 PSX Quantum Stock Terminal")
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Settings")
    symbol = st.sidebar.text_input("Symbol", "FFC").strip().upper()
    start_date = st.sidebar.date_input("Start Date", date(2023, 1, 1))
    end_date = st.sidebar.date_input("End Date", date.today())
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔔 Price Alert")
    alert_price = st.sidebar.number_input("Target Price", value=0.0, min_value=0.0)
    if st.sidebar.button("Set Alert"):
        if alert_price > 0:
            st.session_state["alert"] = {"symbol": symbol, "price": alert_price, "sent": False}
            st.sidebar.success("Alert Set! (sirf tab email aayegi jab ye page khula ho)")
        else:
            st.session_state["alert"] = None
            st.sidebar.info("Alert removed.")

    if start_date >= end_date:
        st.error("Start Date, End Date se pehle honi chahiye.")
        return

    try:
        df = get_history(symbol, start=start_date, end=end_date + timedelta(days=1))
        if df.empty:
            st.error("No data found! Symbol check karein (jaise FFC, OGDC, HBL).")
            return

        df["SMA_20"] = df["Close"].rolling(20).mean()
        df["SMA_50"] = df["Close"].rolling(50).mean()
        df["RSI"] = calculate_rsi(df["Close"])
        last_price = float(df["Close"].iloc[-1])
        last_rsi = df["RSI"].iloc[-1]
        sma20, sma50 = df["SMA_20"].iloc[-1], df["SMA_50"].iloc[-1]
        last_date = df.index[-1].strftime("%Y-%m-%d")

        # Alert (one email only)
        al = st.session_state.get("alert")
        if al and al["symbol"] == symbol and not al["sent"] and abs(last_price - al["price"]) <= last_price * 0.01:
            ok, err = send_email(al["price"], last_price, symbol)
            if ok:
                al["sent"] = True
                st.sidebar.success("📧 Alert email bhej di gayi.")
            else:
                st.sidebar.error(f"Email nahi gayi: {err}")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Price", f"Rs. {last_price:.2f}")
        col1.caption(f"🕒 Last data: {last_date} | Checked: {datetime.now():%H:%M:%S}")
        col2.metric("RSI", "N/A" if pd.isna(last_rsi) else f"{last_rsi:.2f}")

        if pd.isna(sma20) or pd.isna(sma50):
            signal, color = "⚪ NOT ENOUGH DATA", "gray"
        elif last_price > sma20 > sma50:
            signal, color = "🟢 STRONG BUY", "green"
        elif last_price < sma20 < sma50:
            signal, color = "🔴 STRONG SELL", "red"
        else:
            signal, color = "🟡 HOLD", "yellow"
        col3.markdown(f"**Signal:** <h3 style='color:{color};'>{signal}</h3>", unsafe_allow_html=True)

        if pd.isna(last_rsi):
            status = "N/A"
        else:
            status = "Overbought" if last_rsi > 70 else "Oversold" if last_rsi < 30 else "Normal"
        col4.metric("Status", status)

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                            row_heights=[0.6, 0.2, 0.2])
        fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"],
                                     close=df["Close"], name="Price"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA_20"], line=dict(color="cyan"), name="SMA 20"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA_50"], line=dict(color="yellow"), name="SMA 50"), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume", marker_color="gray", opacity=0.5), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], line=dict(color="magenta"), name="RSI"), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
        fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("🏢 Company Intelligence")
        info = get_info(symbol)
        c1, c2 = st.columns(2)
        c1.write(f"**Name:** {info.get('longName', 'N/A')}")
        c1.write(f"**Sector:** {info.get('sector', 'N/A')}")
        mcap = info.get("marketCap")
        c2.write(f"**Market Cap:** {f'{mcap:,}' if isinstance(mcap, (int, float)) else 'N/A'}")
        c2.write(f"**52W High:** {info.get('fiftyTwoWeekHigh', 'N/A')}")

        st.subheader("💰 Dividend History")
        divs = get_dividends(symbol)
        if divs is not None and not divs.empty:
            st.dataframe(divs.tail(10).rename("Dividend"), use_container_width=True)
        else:
            st.write("No dividend data.")

        st.subheader("📰 Live News")
        news = get_news(symbol)
        shown = 0
        for n in news[:5]:
            content = n.get("content", n)  # new and old yfinance formats
            title = content.get("title")
            link = (content.get("canonicalUrl") or {}).get("url") or content.get("clickThroughUrl", {}) and \
                (content.get("clickThroughUrl") or {}).get("url") or n.get("link")
            if title and link:
                st.markdown(f"**[{title}]({link})**")
                shown += 1
        if not shown:
            st.write("No news available.")

    except Exception as e:
        st.error(f"System Error: {e}")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
page = st.session_state["page"]
if page == "admin" and not is_admin:
    page = "user"

if page == "admin":
    show_admin_page()
elif page == "portfolio":
    show_portfolio_page()
else:
    show_analyzer_page()
