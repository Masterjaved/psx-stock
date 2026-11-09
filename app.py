import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date
import smtplib
from email.mime.text import MIMEText
from supabase import create_client, Client

# --- 1. Supabase کنکشن ---
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# پیج کی سیٹنگز
st.set_page_config(page_title="PSX Quantum Terminal", layout="wide")

# --- 2. Auth سسٹم (Login/Signup) ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

def auth_page():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 PSX Quantum Access")
        auth_mode = st.radio("اختیار منتخب کریں", ["Login", "Sign Up"])
        
        email = st.text_input("ای میل (Email)")
        password = st.text_input("پاس ورڈ (Password)", type="password")
        
        if auth_mode == "Login":
            if st.button("Login"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state['user'] = res.user
                    st.success("لاگ ان کامیاب!")
                    st.rerun()
                except Exception as e:
                    st.error(f"لاگ ان ناکام: {e}")
        else:
            if st.button("Create Account"):
                try:
                    res = supabase.auth.sign_up({"email": email, "password": password})
                    st.success("اکاؤنٹ بن گیا! براہ کرم اپنی ای میل چیک کریں اور تصدیق (Verify) کریں۔")
                except Exception as e:
                    st.error(f"سائن اپ میں غلطی: {e}")

if st.session_state['user'] is None:
    auth_page()
    st.stop()

# --- 3. لاگ آؤٹ بٹن ---
if st.sidebar.button("Logout"):
    st.session_state['user'] = None
    st.rerun()

# UI ڈیزائن
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4253; }
    </style>
    """, unsafe_allow_html=True)

st.title(f"🚀 PSX Quantum Terminal | Welcome {st.session_state['user'].email}")

# --- 4. ای میل الرٹ فنکشن ---
def send_email(target_price, current_price, symbol):
    try:
        sender_email = st.secrets["SENDER_EMAIL"] 
        receiver_email = st.secrets["RECEIVER_EMAIL"]
        app_password = st.secrets["APP_PASSWORD"]

        msg = MIMEText(f"الرٹ! {symbol} کی قیمت آپ کے ٹارگٹ {target_price} کے قریب پہنچ گئی ہے۔\nموجودہ قیمت: {current_price}")
        msg['Subject'] = f"PSX Price Alert: {symbol}"
        msg['From'] = sender_email
        msg['To'] = receiver_email

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"ای میل ایرر: {e}")
        return False

# --- 5. سائیڈ بار ---
st.sidebar.header("⚙️ ٹرمینل سیٹنگز")
symbol = st.sidebar.text_input("کمپنی کا سمبل", "FFC").upper()
start_date = st.sidebar.date_input("شروع کی تاریخ", date(2023, 1, 1))
end_date = st.sidebar.date_input("آخری تاریخ", date.today())

st.sidebar.markdown("---")
st.sidebar.subheader("🔔 پرائس الرٹ")
alert_price = st.sidebar.number_input("ٹارگٹ قیمت", value=0.0)
if st.sidebar.button("الرٹ ایکٹو کریں"):
    st.sidebar.success("الرٹ سیٹ ہو گیا!")

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 6. مین اینالیسس ---
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
        col1.metric("موجودہ قیمت", f"Rs. {last_price:.2f}")
        col2.metric("RSI", f"{df['RSI'].iloc[-1]:.2f}")
        
        if last_price > df['SMA_20'].iloc[-1] and df['SMA_20'].iloc[-1] > df['SMA_50'].iloc[-1]:
            signal, sig_color = "🟢 STRONG BUY", "green"
        elif last_price < df['SMA_20'].iloc[-1] and df['SMA_20'].iloc[-1] < df['SMA_50'].iloc[-1]:
            signal, sig_color = "🔴 STRONG SELL", "red"
        else:
            signal, sig_color = "🟡 HOLD", "yellow"
            
        col3.markdown(f"**سگنل:** <h3 style='color:{sig_color};'>{signal}</h3>", unsafe_allow_html=True)
        col4.metric("سٹیٹس", "Overbought" if df['RSI'].iloc[-1] > 70 else "Oversold" if df['RSI'].iloc[-1] < 30 else "Normal")

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='cyan'), name="SMA 20"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='yellow'), name="SMA 50"), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='gray', opacity=0.5), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name="RSI"), row=3, col=1)
        fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("🏢 کمپنی کی تفصیلات")
        info = stock_obj.info
        c1, c2 = st.columns(2)
        c1.write(f"**نام:** {info.get('longName', 'N/A')}")
        c1.write(f"**سیکٹر:** {info.get('sector', 'N/A')}")
        c2.write(f"**مارکیٹ کیپ:** {info.get('marketCap', 'N/A')}")
        c2.write(f"**52 ہفتہ ہائی:** {info.get('fiftyTwoWeekHigh', 'N/A')}")

        st.subheader("💰 ڈیویڈنڈ")
        st.write(stock_obj.dividends.tail(10))

        st.subheader("📰 خبریں")
        for item in stock_obj.news[:5]:
            st.markdown(f"**[{item['title']}]({item['link']})**")

except Exception as e:
    st.error(f"ایرر: {e}")
