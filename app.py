import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date

# پیج کی سیٹنگز
st.set_page_config(page_title="PSX Quantum Analyzer", layout="wide")

# کسٹم سی ایس ایس
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4253; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 PSX Quantum Stock Terminal")
st.markdown("پروفیشنل ٹیکنیکل انالیسس اور الگورتھمک سگنلز")

# سائیڈ بار
st.sidebar.header("⚙️ ٹرمینل سیٹنگز")
symbol = st.sidebar.text_input("کمپنی کا سمبل", "FFC").upper()
start_date = st.sidebar.date_input("شروع کی تاریخ", date(2023, 1, 1))
end_date = st.sidebar.date_input("آخری تاریخ", date.today())
sma_fast = st.sidebar.slider("Fast SMA (چھوٹی لائن)", 5, 50, 20)
sma_slow = st.sidebar.slider("Slow SMA (بڑی لائن)", 20, 200, 50)

# RSI کیلکولیشن کا فنکشن
def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

try:
    # ڈیٹا لوڈ کریں
    full_symbol = symbol + ".KA"
    stock_obj = yf.Ticker(full_symbol)
    df = stock_obj.history(start=start_date, end=end_date)

    if df.empty:
        st.error("ڈیٹا نہیں ملا! براہ کرم درست سمبل لکھیں۔")
    else:
        # --- کیلکولیشنز ---
        df['SMA_Fast'] = df['Close'].rolling(window=sma_fast).mean()
        df['SMA_Slow'] = df['Close'].rolling(window=sma_slow).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        
        last_price = df['Close'].iloc[-1]
        last_rsi = df['RSI'].iloc[-1]
        
        # ایڈوانس سگنل لاجک
        if last_price > df['SMA_Fast'].iloc[-1] and df['SMA_Fast'].iloc[-1] > df['SMA_Slow'].iloc[-1]:
            signal = "🟢 STRONG BUY (مضبوط خریداری)"
            signal_color = "#00ff00"
        elif last_price < df['SMA_Fast'].iloc[-1] and df['SMA_Fast'].iloc[-1] < df['SMA_Slow'].iloc[-1]:
            signal = "🔴 STRONG SELL (مضبوط فروخت)"
            signal_color = "#ff0000"
        else:
            signal = "🟡 HOLD / NEUTRAL (انتظار کریں)"
            signal_color = "#ffff00"

        # --- ٹاپ ڈیش بورڈ ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("موجودہ قیمت", f"Rs. {last_price:.2f}")
        col2.metric("RSI (14)", f"{last_rsi:.2f}")
        col3.markdown(f"**سگنل:** <h3 style='color:{signal_color};'>{signal}</h3>", unsafe_allow_html=True)
        
        rsi_status = "Overbought (مہنگا)" if last_rsi > 70 else "Oversold (سستا)" if last_rsi < 30 else "Normal"
        col4.metric("مارکیٹ سٹیٹس", rsi_status)

        # --- پروفیشنل چارٹ (Subplots) ---
        # ہم 3 حصے بنائیں گے: قیمت (Price), والیم (Volume), اور RSI
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, 
                           row_heights=[0.6, 0.2, 0.2])

        # 1. Candlestick Chart
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_Fast'], line=dict(color='cyan', width=1), name=f'Fast SMA {sma_fast}'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_Slow'], line=dict(color='yellow', width=1), name=f'Slow SMA {sma_slow}'), row=1, col=1)

        # 2. Volume Chart
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='gray', opacity=0.5), row=2, col=1)

        # 3. RSI Chart
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2), name="RSI"), row=3, col=1)
        # RSI Threshold lines
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

        fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- ٹیبز سسٹم (Tabs) ---
        tab1, tab2, tab3 = st.tabs(["🏢 کمپنی کی تفصیلات", "💰 ڈیویڈنڈ ہسٹری", "📰 لائیو نیوز"])
        
        with tab1:
            info = stock_obj.info
            c1, c2 = st.columns(2)
            c1.write(f"**مکمل نام:** {info.get('longName', 'N/A')}")
            c1.write(f"**سیکٹر:** {info.get('sector', 'N/A')}")
            c2.write(f"**مارکیٹ کیپ:** {info.get('marketCap', 'N/A')}")
            c2.write(f"**52 ہفتہ ہائی:** {info.get('fiftyTwoWeekHigh', 'N/A')}")

        with tab2:
            div_yield = info.get('dividendYield', 0)
            if div_yield:
                st.success(f"Dividend Yield: {div_yield*100:.2f}%")
            st.write(stock_obj.dividends.tail(10))

        with tab3:
            news = stock_obj.news
            if news:
                for item in news[:5]:
                    st.markdown(f"**[{item['title']}]({item['link']})**")
            else:
                st.write("کوئی خبر دستیاب نہیں ہے۔")

except Exception as e:
    st.error(f"ایرر: {e}")
