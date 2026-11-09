import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date
import smtplib
from email.mime.text import MIMEText

# پیج کی بنیادی سیٹنگز
st.set_page_config(page_title="PSX Quantum Terminal", layout="wide")

# --- 1. لاگ ان سسٹم (Login System) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login_page():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 PSX Terminal Login")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            # پاس ورڈ Secrets سے چیک ہو رہا ہے
            if user == "admin" and pwd == st.secrets["ADMIN_PASSWORD"]:
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("غلط یوزر نیم یا پاس ورڈ!")

if not st.session_state['logged_in']:
    login_page()
    st.stop()

# --- 2. لاگ آؤٹ بٹن (Sidebar) ---
st.sidebar.button("Logout", on_click=lambda: st.session_state.update({"logged_in": False}))

# خوبصورت UI کے لیے CSS
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4253; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 PSX Quantum Stock Terminal")
st.markdown("پروفیشنل ٹیکنیکل انالیسس اور سیکیور الرٹ سسٹم")

# --- 3. ای میل الرٹ فنکشن (Email Logic) ---
def send_email(target_price, current_price, symbol):
    try:
        # تمام معلومات Secrets سے اٹھائی جا رہی ہیں
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
        st.error(f"ای میل بھیجنے میں غلطی: {e}")
        return False

# --- 4. سائیڈ بار (Settings) ---
st.sidebar.header("⚙️ ٹرمینل سیٹنگز")
symbol = st.sidebar.text_input("کمپنی کا سمبل (مثلاً FFC, SYS, ENGRO)", "FFC").upper()
start_date = st.sidebar.date_input("شروع کی تاریخ", date(2023, 1, 1))
end_date = st.sidebar.date_input("آخری تاریخ", date.today())

st.sidebar.markdown("---")
st.sidebar.subheader("🔔 پرائس الرٹ")
alert_price = st.sidebar.number_input("ٹارگٹ قیمت لکھیں", value=0.0)
if st.sidebar.button("الرٹ ایکٹو کریں"):
    st.sidebar.success("الرٹ سیٹ ہو گیا! قیمت پہنچنے پر میل آئے گی۔")

# RSI کیلکولیشن کا فارمولا
def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 5. مین پروگرام (Main Logic) ---
try:
    full_symbol = symbol + ".KA"
    stock_obj = yf.Ticker(full_symbol)
    df = stock_obj.history(start=start_date, end=end_date)

    if df.empty:
        st.error("ڈیٹا نہیں ملا! براہ کرم درست سمبل لکھیں۔")
    else:
        # ٹیکنیکل انڈیکیٹرز
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        
        last_price = df['Close'].iloc[-1]
        last_rsi = df['RSI'].iloc[-1]
        
        # ای میل چیک (اگر قیمت ٹارگٹ کے 1% کے قریب ہو)
        if alert_price > 0 and abs(last_price - alert_price) < (last_price * 0.01):
            if send_email(alert_price, last_price, symbol):
                st.success("🎯 قیمت ٹارگٹ پر پہنچ گئی! آپ کو ای میل بھیج دی گئی ہے۔")

        # ٹاپ میٹرکس
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("موجودہ قیمت", f"Rs. {last_price:.2f}")
        col2.metric("RSI (14)", f"{last_rsi:.2f}")
        
        # سگنل لاجک
        if last_price > df['SMA_20'].iloc[-1] and df['SMA_20'].iloc[-1] > df['SMA_50'].iloc[-1]:
            signal = "🟢 STRONG BUY"
            sig_color = "green"
        elif last_price < df['SMA_20'].iloc[-1] and df['SMA_20'].iloc[-1] < df['SMA_50'].iloc[-1]:
            signal = "🔴 STRONG SELL"
            sig_color = "red"
        else:
            signal = "🟡 HOLD / NEUTRAL"
            sig_color = "yellow"
            
        col3.markdown(f"**سگنل:** <h3 style='color:{sig_color};'>{signal}</h3>", unsafe_allow_html=True)
        
        rsi_stat = "Overbought (مہنگا)" if last_rsi > 70 else "Oversold (سستا)" if last_rsi < 30 else "Normal"
        col4.metric("مارکیٹ سٹیٹس", rsi_stat)

        # --- پروفیشنل چارٹ (Subplots) ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
        
        # Price + SMA
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='cyan', width=1), name="SMA 20"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='yellow', width=1), name="SMA 50"), row=1, col=1)
        
        # Volume
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='gray', opacity=0.5), row=2, col=1)
        
        # RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2), name="RSI"), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

        fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- کمپنی ڈیٹا (No Tabs, just simple list) ---
        st.markdown("---")
        st.subheader("🏢 کمپنی کی تفصیلات")
        info = stock_obj.info
        c1, c2 = st.columns(2)
        c1.write(f"**مکمل نام:** {info.get('longName', 'N/A')}")
        c1.write(f"**سیکٹر:** {info.get('sector', 'N/A')}")
        c2.write(f"**مارکیٹ کیپ:** {info.get('marketCap', 'N/A')}")
        c2.write(f"**52 ہفتہ ہائی:** {info.get('fiftyTwoWeekHigh', 'N/A')}")

        st.markdown("---")
        st.subheader("💰 ڈیویڈنڈ ہسٹری")
        div_yield = info.get('dividendYield', 0)
        if div_yield:
            st.success(f"Dividend Yield: {div_yield*100:.2f}%")
        st.write(stock_obj.dividends.tail(10))

        st.markdown("---")
        st.subheader("📰 تازہ ترین خبریں")
        news = stock_obj.news
        if news:
            for item in news[:5]:
                st.markdown(f"**[{item['title']}]({item['link']})**")
        else:
            st.write("کوئی خبر دستیاب نہیں ہے۔")

except Exception as e:
    st.error(f"ایک تکنیکی غلطی ہوئی ہے: {e}")
