import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import date

# پیج کی سیٹنگز
st.set_page_config(page_title="PSX Pro Analyzer", layout="wide")

# کسٹم سی ایس ایس (UI کو خوبصورت بنانے کے لیے)
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4253; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 PSX Pro Stock Analyzer & Signal Bot")
st.markdown("پاکستان سٹاک ایکسچینج کے لیے پروفیشنل تجزیہ اور ٹریڈنگ سگنلز")

# سائیڈ بار
st.sidebar.header("⚙️ کنٹرول پینل")
symbol = st.sidebar.text_input("کمپنی کا سمبل (مثلاً FFC, ENGRO, SYS)", "FFC").upper()
start_date = st.sidebar.date_input("شروع کی تاریخ", date(2023, 1, 1))
end_date = st.sidebar.date_input("آخری تاریخ", date.today())
sma_days = st.sidebar.slider("Moving Average (SMA) کے دن", 5, 100, 20)

# ڈیٹا لوڈ کرنے کا فنکشن
def load_data(ticker):
    full_symbol = ticker + ".KA"
    stock = yf.Ticker(full_symbol)
    df = stock.history(start=start_date, end=end_date)
    return df, stock

try:
    df, stock_obj = load_data(symbol)

    if df.empty:
        st.error("ڈیٹا نہیں ملا! براہ کرم سمبل چیک کریں (مثلاً FFC)۔")
    else:
        # --- ٹیکنیکل کیلکولیشنز ---
        df['SMA'] = df['Close'].rolling(window=sma_days).mean()
        last_price = df['Close'].iloc[-1]
        last_sma = df['SMA'].iloc[-1]
        
        # خرید و فروخت کا سگنل
        if last_price > last_sma:
            signal = "🟢 BUY (خریدیں)"
            signal_color = "green"
            advice = "قیمت SMA سے اوپر ہے، مارکیٹ میں تیزی کا امکان ہے۔"
        else:
            signal = "🔴 SELL (بیچیں)"
            signal_color = "red"
            advice = "قیمت SMA سے نیچے ہے، مارکیٹ میں مندی کا امکان ہے۔"

        # --- ٹاپ میٹرکس (Top Dashboard) ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("موجودہ قیمت", f"Rs. {last_price:.2f}")
        col2.metric("SMA {sma_days}", f"Rs. {last_sma:.2f}")
        col3.markdown(f"**ٹریڈنگ سگنل:** <h3 style='color:{signal_color};'>{signal}</h3>", unsafe_allow_html=True)
        col4.write(f"**مشورہ:** {advice}")

        # --- کینڈل سٹک چارٹ (Candlestick Chart) ---
        st.subheader("📈 پروفیشنل پرائس چارٹ")
        fig = go.Figure()
        # Candlestick
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
        # SMA Line
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA'], line=dict(color='orange', width=2), name=f'SMA {sma_days}'))
        
        fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=500)
        st.plotly_chart(fig, use_container_width=True)

        # --- ڈیویڈنڈ اور کمپنی کی معلومات ---
        st.markdown("---")
        col_info, col_div = st.columns(2)
        
        with col_info:
            st.subheader("🏢 کمپنی کی تفصیلات")
            info = stock_obj.info
            st.write(f"**کمپنی کا نام:** {info.get('longName', 'N/A')}")
            st.write(f"**سیکٹر:** {info.get('sector', 'N/A')}")
            st.write(f"**مارکیٹ کیپ:** {info.get('marketCap', 'N/A')}")

        with col_div:
            st.subheader("💰 ڈیویڈنڈ کی معلومات")
            div_yield = info.get('dividendYield', 0)
            if div_yield:
                st.success(f"یہ کمپنی ڈیویڈنڈ دے رہی ہے! ییلڈ: {div_yield*100:.2f}%")
            else:
                st.warning("اس وقت کوئی ڈیویڈنڈ ڈیٹا دستیاب نہیں ہے۔")
            
            # حالیہ ڈیویڈنڈز کی لسٹ
            st.write("**حالیہ ڈیویڈنڈز:**")
            st.write(stock_obj.dividends.tail(5))

        # --- تازہ ترین خبریں ---
        st.markdown("---")
        st.subheader("📰 تازہ ترین خبریں")
        news = stock_obj.news
        if news:
            for item in news[:5]:
                st.markdown(f"**[{item['title']}]({item['link']})**")
        else:
            st.write("کوئی تازہ خبر دستیاب نہیں ہے۔")

except Exception as e:
    st.error(f"ایک غلطی ہوئی ہے: {e}")
