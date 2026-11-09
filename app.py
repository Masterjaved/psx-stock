import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date
import smtplib
from email.mime.text import MIMEText
from supabase import create_client, Client

# --- 1. بنیادی سیٹنگز ---
st.set_page_config(page_title="PSX Quantum Terminal", layout="wide", page_icon="🚀")

# Supabase کنکشنز
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
    service_key = st.secrets["SUPABASE_SERVICE_KEY"]
    supabase_admin: Client = create_client(url, service_key)
except Exception as e:
    st.error("Secrets میں Supabase کی معلومات درست نہیں ہیں۔")
    st.stop()

if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'page' not in st.session_state:
    st.session_state['page'] = "user"

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4253; }
    .admin-box { background-color: #2d1b4e; padding: 20px; border-radius: 15px; border: 2px solid #8a2be2; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Auth سسٹم ---
def auth_page():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 PSX Quantum Access")
        auth_mode = st.radio("اختیار منتخب کریں", ["Login", "Sign Up"], horizontal=True)
        email = st.text_input("ای میل (Email)")
        password = st.text_input("پاس ورڈ (Password)", type="password")
        if auth_mode == "Login":
            if st.button("Login", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state['user'] = res.user
                    st.rerun()
                except Exception as e: st.error(f"لاگ ان ناکام: {e}")
        else:
            if st.button("Create Account", use_container_width=True):
                try:
                    supabase.auth.sign_up({"email": email, "password": password})
                    st.success("اکاؤنٹ بن گیا! ای میل Verify کریں۔")
                except Exception as e: st.error(f"سائن اپ میں غلطی: {e}")

if st.session_state['user'] is None:
    auth_page()
    st.stop()

# --- 3. نیویگیشن ---
st.sidebar.header(f"👋 {st.session_state['user'].email}")
st.sidebar.markdown("---")
is_admin = st.session_state['user'].email == st.secrets["ADMIN_EMAIL"]

if is_admin:
    st.sidebar.success("👑 Admin Access")
    if st.sidebar.button("🛡️ Admin Dashboard"): st.session_state['page'] = "admin"
else:
    st.sidebar.info("👤 User Mode")
    st.session_state['page'] = "user"

if st.sidebar.button("📊 Stock Analyzer"): st.session_state['page'] = "user"
if st.sidebar.button("💼 My Portfolio"): st.session_state['page'] = "portfolio"
if st.sidebar.button("Logout"):
    st.session_state['user'] = None
    st.rerun()

# --- 4. ہیلپر فنکشنز ---
def send_email(target_price, current_price, symbol):
    try:
        sender = st.secrets["SENDER_EMAIL"]
        receiver = st.secrets["RECEIVER_EMAIL"]
        pwd = st.secrets["APP_PASSWORD"]
        msg = MIMEText(f"الرٹ! {symbol} کی قیمت آپ کے ٹارگٹ {target_price} کے قریب ہے۔ موجودہ قیمت: {current_price}")
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

# --- 5. مین پیجز ---
if st.session_state['page'] == "admin":
    st.markdown('<div class="admin-box">', unsafe_allow_html=True)
    st.title("🛡️ Admin Control Center")
    try:
        response = supabase_admin.auth.admin.list_users()
        user_list = [user.email for user in response.users]
        st.table(pd.DataFrame({"User Email": user_list}))
    except Exception as e: st.error(f"غلطی: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state['page'] == "portfolio":
    st.title("💼 My Stock Portfolio")
    
    # پورٹ فولیو میں سٹاک شامل کرنا
    with st.expander("➕ Add Stock to Portfolio"):
        col1, col2, col3 = st.columns(3)
        p_symbol = col1.text_input("Symbol (مثلاً FFC)").upper()
        p_qty = col2.number_input("Quantity", min_value=1, step=1)
        p_price = col3.number_input("Buy Price", min_value=0.1)
        if st.button("Save to Portfolio"):
            try:
                supabase.table("portfolios").insert({
                    "user_id": st.session_state['user'].id,
                    "symbol": p_symbol,
                    "quantity": p_qty,
                    "buy_price": p_price
                }).execute()
                st.success("پورٹ فولیو میں محفوظ کر لیا گیا!")
            except Exception as e: st.error(f"غلطی: {e}")

    # پورٹ فولیو دکھانا
    try:
        res = supabase.table("portfolios").select("*").eq("user_id", st.session_state['user'].id).execute()
        if res.data:
            df_p = pd.DataFrame(res.data)
            st.table(df_p[['symbol', 'quantity', 'buy_price']])
        else:
            st.write("آپ کا پورٹ فولیو ابھی خالی ہے۔")
    except Exception as e: st.error(f"ڈیٹا لوڈ کرنے میں غلطی: {e}")

else:
    st.title("🚀 PSX Quantum Stock Terminal")
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Settings")
    symbol = st.sidebar.text_input("کمپنی کا سمبل", "FFC").upper()
    start_date = st.sidebar.date_input("شروع کی تاریخ", date(2023, 1, 1))
    end_date = st.sidebar.date_input("آخری تاریخ", date.today())
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔔 Price Alert")
    alert_price = st.sidebar.number_input("ٹارگٹ قیمت", value=0.0)
    if st.sidebar.button("Set Alert"): st.sidebar.success("الرٹ سیٹ ہو گیا!")

    try:
        full_symbol = symbol + ".KA"
        stock_obj = yf.Ticker(full_symbol)
        df = stock_obj.history(start=start_date, end=end_date)
        if df.empty:
            st.error("ڈیٹا نہیں ملا!")
        else:
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['RSI'] = calculate_rsi(df['Close'])
            last_price = df['Close'].iloc[-1]
            
            if alert_price > 0 and abs(last_price - alert_price) < (last_price * 0.01):
                send_email(alert_price, last_price, symbol)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Price", f"Rs. {last_price:.2f}")
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
            c2.write(f"**52W High:** {info.get('fiftyTwoWeekHigh', 'N/A')}")
            st.subheader("💰 Dividend History")
            st.write(stock_obj.dividends.tail(10))
            st.subheader("📰 Live News")
            if stock_obj.news:
                for item in stock_obj.news[:5]: st.markdown(f"**[{item['title']}]({item['link']})**")
            else: st.write("کوئی خبر دستیاب نہیں ہے۔")

except Exception as e:
    st.error(f"System Error: {e}")
