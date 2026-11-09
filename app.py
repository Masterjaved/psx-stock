import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import date

# پیج کی سیٹنگز
st.set_page_config(page_title="PSX Stock Analyzer", layout="wide")

st.title("📈 پاکستان سٹاک ایکسچینج (PSX) اینالائزر")
st.markdown("اس ایپ کے ذریعے آپ کسی بھی PSX کمپنی کا ڈیٹا اور ٹرینڈ دیکھ سکتے ہیں۔")

# سائیڈ بار (Sidebar) میں ان پٹس
st.sidebar.header("سیٹنگز")
symbol = st.sidebar.text_input("کمپنی کا سمبل لکھیں (مثلاً ENGRO, LUCK, SYS)", "ENGRO").upper()
start_date = st.sidebar.date_input("شروع کی تاریخ", date(2023, 1, 1))
end_date = st.sidebar.date_input("آخری تاریخ", date.today())
sma_days = st.sidebar.slider("Moving Average (SMA) کے دن", 5, 100, 20)

# ڈیٹا حاصل کرنے کا فنکشن
def load_data(ticker):
    full_symbol = ticker + ".KA"
    data = yf.download(full_symbol, start=start_date, end=end_date)
    return data

try:
    # ڈیٹا لوڈ کریں
    df = load_data(symbol)

    if df.empty:
        st.error("ڈیٹا نہیں ملا! براہ کرم درست سمبل چیک کریں یا تاریخ بدلیں۔")
    else:
        # Moving Average کی کیلکولیشن
        df['SMA'] = df['Close'].rolling(window=sma_days).mean()

        # --- گراف بنانا (Plotly) ---
        fig = go.Figure()

        # کلوزنگ پرائس کی لائن
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', name='Closing Price', line=dict(color='blue')))
        
        # SMA کی لائن
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA'], mode='lines', name=f'SMA {sma_days}', line=dict(color='orange')))

        fig.update_layout(
            title=f"{symbol} کا سٹاک ٹرینڈ",
            xaxis_title="تاریخ",
            yaxis_title="قیمت (PKR)",
            template="plotly_white",
            hovermode="x unified"
        )

        # ایپ میں گراف دکھانا
        st.plotly_chart(fig, use_container_width=True)

        # ڈیٹا ٹیبل دکھانا
        st.subheader("تازہ ترین ڈیٹا")
        st.write(df.tail(10))

        # ڈاؤن لوڈ بٹن
        csv = df.to_csv().encode('utf-8')
        st.download_button("ڈیٹا ڈاؤن لوڈ کریں (CSV)", data=csv, file_name=f"{symbol}_data.csv", mime='text/csv')

except Exception as e:
    st.error(f"ایک غلطی ہوئی ہے: {e}")
