import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, datetime
import smtplib
from email.mime.text import MIMEText
from supabase import create_client, Client

st.set_page_config(page_title="PSX Quantum Terminal", layout="wide", page_icon="🚀")

def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        client = create_client(url, key)
        s_key = st.secrets["SUPABASE_SERVICE_KEY"]
        admin_client = create_client(url, s_key)
        return client, admin_client
    except Exception as e:
        st.error("Supabase Secrets Error")
        return None, None

supabase, supabase_admin = init_supabase()
if not supabase:
    st.stop()

if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'page' not in st.session_state:
    st.session_state['page'] = "user"
if 'edit_id' not in st.session_state:
    st.session_state['edit_id'] = None

# --- Auth Page ---
def auth_page():
    st.title("🔐 PSX Quantum Access")
    auth_mode = st.radio("Select Option", ["Login", "Sign Up"], horizontal=True)
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if auth_mode == "Login":
        if st.button("Login", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state['user'] = res.user
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")
    else:
        if st.button("Create Account", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.success("Account created! Please verify email.")
            except Exception as e: st.error(f"Error: {e}")

if st.session_state['user'] is None:
    auth_page()
    st.stop()

# --- Navigation ---
st.sidebar.header(f"User: {st.session_state['user'].email}")
is_admin = st.session_state['user'].email == st.secrets["ADMIN_EMAIL"]

if is_admin:
    if st.sidebar.button("🛡️ Admin Dashboard"):
        st.session_state['page'] = "admin"
else:
    st.session_state['page'] = "user"

if st.sidebar.button("📊 Stock Analyzer"):
    st.session_state['page'] = "user"
if st.sidebar.button("💼 My Portfolio"):
    st.session_state['page'] = "portfolio"
if st.sidebar.button("Logout"):
    st.session_state['user'] = None
    st.rerun()

# --- Helpers ---
def send_email(target_price, current_price, symbol):
    try:
        sender = st.secrets["SENDER_EMAIL"]
        receiver = st.session_state['user'].email
        pwd = st.secrets["APP_PASSWORD"]
        msg = MIMEText(f"Alert! {symbol} is near target {target_price}. Current: {current_price}")
        msg['Subject'] = f"PSX Alert: {symbol}"
        msg['From'] = sender
        msg['To'] = receiver
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, pwd)
            server.send_message(msg)
        return True
    except: return False

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- Admin Page ---
def show_admin_page():
    st.title("🛡️ Admin Control Center")
    try:
        response = supabase_admin.auth.admin.list_users()
        user_list = [user.email for user in response.users]
        st.table(pd.DataFrame({"User Email": user_list}))
    except Exception as e: st.error(f"Error: {e}")

# --- Portfolio Page ---
def show_portfolio_page():
    st.title("💼 Intelligent Portfolio")
    
    if st.session_state['edit_id'] is not None:
        st.subheader("✏️ Edit Stock")
        try:
            res = supabase.table("portfolios").select("*").eq("id", st.session_//_state['edit_id']).single().execute()
            # Fix: Changed to la-S_STATE for safety
            res = supabase.table("portfolios").select("*").eq("id", st.session_state['edit_id']).single().execute()
            item = res.data
            col_e1, col_e2, col_e3, col_e4 = st.columns([1, 1, 1, 1])
            e_symbol = col_e1.text_input("Symbol", value=item['symbol']).upper()
            e_qty = col_e2.number_input("Quantity", value=int(item['quantity']), min_value=1)
            e_price = col_e3.number_input("Buy Price", value=float(item['buy_price']), min_value=0.1)
            e_shariah = col_e4.selectbox("Shariah", ["Compliant", "Non-Compliant"], index=0 if item.get('shariah') == "Compliant" else 1)
            if st.button("Update"):
                supabase.table("portfolios").update({"symbol": e_symbol, "quantity": e_qty, "buy_price": e_price, "shariah": e_shariah}).eq("id", st.session_state['edit_id']).execute()
                st.session_state['edit_id'] = None
                st.rerun()
            if st.button("Cancel"):
                st.session_state['edit_id'] = None
                st.rerun()
        except Exception as e: st.error(f"Error: {e}")
    else:
        with st.expander("➕ Add Stock"):
            with st.form("add_form"):
                col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
                p_symbol = col1.text_input("Symbol").upper()
                p_qty = col2.number_input("Quantity", min_value=1, step=1)
                p_price = col3.number_input("Buy Price", min_//_value=0.1)
                p_price = col3.number_input("Buy Price", min_value=0.1)
                p_shariah = col4.selectbox("Shariah Status", ["Compliant", "Non-Compliant"])
                if st.form_submit_button("Save"):
                    try:
                        supabase.table("portfolios").insert({"user_id": st.session_state['user'].id, "symbol": p_symbol, "quantity": p_qty, "buy_price": p_price, "shariah": p_shariah}).execute()
                        st.success("Saved!")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

        try:
            res = supabase.table("portfolios").select("*").eq("user_id", st.session_state['user'].id).execute()
            if res.data:
                total_inv, total_cur = 0, 0
                for item in res.data:
                    try:
                        s_sym = item['symbol'] + ".KA"
                        s_obj = yf.Ticker(s_sym)
                        s_df = s_obj.history(period="1mo")
                        if not s_df.empty:
                            curr_p = s_df['Close'].iloc[-1]
                            b_p, q = item['buy_price'], item['quantity']
                            pl = (curr_p - b_p) * q
                            div_y = s_obj.info.get('dividendYield', 0) or 0
                            s_df['SMA_20'] = s_df['Close'].rolling(window=20).mean()
                            s_df['SMA_50'] = s_df['Close'].rolling(window=50).mean()
                            sma20, sma50 = s_df['SMA_20'].iloc[-1], s_df['SMA_50'].iloc[-1]
                            if curr_p > sma20 and sma20 > sma50: advice, a_color = "🟢 Buy More", "green"
                            elif curr_p < sma20 and sma20 < sma50: advice, a_color = "🔴 Sell / Exit", "red"
                            else: advice, a_color = "🟡 Hold", "yellow"
                            total_inv += (b_p * q)
                            total_cur += (curr_p * q)
                            c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1.5, 1.5, 1, 1])
                            c1.write(f"**{item['symbol']}**")
                            sh_c = "green" if item.get('shariah') == "Compliant" else "red"
                            c2.markdown(f"<span style='color:{sh_c}; font-size:12px;'>● {item.get('shariah', 'Unknown')}</span>", unsafe_allow_html=True)
                            c3.write(f"P&L: {'📈' if pl > 0 else '📉'} Rs. {pl:.2f}")
                            c4.markdown(f"<span style='color:{a_color}; font-weight:bold;'>{advice}</span>", unsafe_allow_//_html=True)
                            c4.markdown(f"<span style='color:{a_color}; font-weight:bold;'>{advice}</span>", unsafe_allow_html=True)
                            c5.write(f"Div: {div_y*100:.1f}%")
                            if c6.button("🗑️", key=f"dl_{item['id']}"):
                                supabase.table("portfolios").delete().eq("id", item['id']).execute()
                                st.rerun()
                            with st.expander("Details"):
                                st.write(f"Buy: {b_p} | Current: {curr_p:.2f}")
                                if st.button("Edit", key=f"ed_{item['id']}"):
                                    st.session_state['edit_id'] = item['id']
                                    st.rerun()
                            st.markdown("---")
                    except: pass
                c_inv, c_cur, c_net = st.columns(3)
                c_inv.metric("Total Invested", f"Rs. {total_inv:,.2f}")
                c_cur.metric("Current Value", f"Rs. {total_cur:,.2f}")
                net_pl = total_cur - total_inv
                c_net.metric("Net P&L", f"Rs. {net_pl:,.2f}", delta=f"{net_pl:,.2f}")
            else:
                st.write("Portfolio is empty.")
        except Exception as e: st.error(f"Error: {e}")

# --- 7. Analyzer Page ---
def show_analyzer_page():
    st.title("🚀 PSX Quantum Stock Terminal")
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Settings")
    symbol = st.sidebar.text_input("Symbol", "FFC").upper()
    start_date = st.sidebar.date_input("Start Date", date(2023, 1, 1))
    end_date = st.sidebar.date_input("End Date", date.today())
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔔 Price Alert")
    alert_price = st.sidebar.number_input("Target Price", value=0.0)
    if st.sidebar.button("Set Alert"): st.sidebar.success("Alert Set!")

    try:
        full_symbol = symbol + ".KA"
        stock_obj = yf.Ticker(full_symbol)
        df = stock_obj.history(start=start_date, end=end_date)
        if df.empty:
            st.error("No data found!")
        else:
            last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['RSI'] = calculate_rsi(df['Close'])
            last_price = df['Close'].iloc[-1]
            if alert_price > 0 and abs(last_price - alert_price) < (last_price * 0.01):
                send_email(alert_price, last_price, symbol)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Price", f"Rs. {last_price:.2f}")
            col1.caption(f"🕒 Updated: {last_updated}")
            col2.metric("RSI", f"{df['RSI'].iloc[-1]:.2f}")
            if last_price > df['SMA_20'].iloc[-1] and df['SMA_20'].iloc[-1] > df['SMA_50'].iloc[-1]:
                signal, color = "🟢 STRONG BUY", "green"
            elif last_price < df['SMA_20'].iloc[-1] and df['SMA_20'].iloc[-1] < df['SMA_50'].iloc[-1]:
                signal, color = "🔴 STRONG SELL", "red"
            else:
                signal, color = "🟡 HOLD", "yellow"
            col3.markdown(f"**Signal:** <h3 style='color:{color};'>{signal}</h3>", unsafe_allow_html=True)
            col4.metric("Status", "Overbought" if df['RSI'].iloc[-1] > 70 else "Oversold" if df['RSI'].iloc[-1] < 30 else "Normal")

            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='cyan'), name="SMA 20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='yellow'), name="SMA 50"), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='gray', opacity=0.5), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name="RSI"), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
            fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("---")
            st.subheader("🏢 Company Intelligence")
            info = stock_obj.info
            c1, c2 = st.columns(2)
            c1.write(f"**Name:** {info.get('longName', 'N/A')}")
            c1.write(f"**Sector:** {info.get('sector', 'N/A')}")
            c2.write(f"**Market Cap:** {info.get('marketCap', 'N/A')}")
            c2.write(f"**52W High:** {info.get('fiftyTwoWeekH', 'N/A')}")
            st.subheader("💰 Dividend History")
            st.write(stock_obj.dividends.tail(10))
            st.subheader("📰 Live News")
            if stock_obj.news:
                for item in stock_obj.news[:5]: st.markdown(f"**[{item['title']}]({item['link']})**")
            else: st.write("No news available.")
    except Exception as e:
        st.error(f"System Error: {e}")

# --- 6. Page Router ---
if st.session_state['page'] == "admin":
    show_admin_page()
elif st.session_state['page'] == "portfolio":
    show_portfolio_page()
else:
    show_analyzer_page()
