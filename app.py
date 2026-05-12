import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. ACCESS SECRETS ---
try:
    AV_KEY = st.secrets["AV_KEY"]
except:
    st.error("Please add 'AV_KEY' to your Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="ETF Flow Tracker 2026", layout="wide")
ticker = st.sidebar.text_input("Enter Ticker", "SPY").upper()

# --- 2. THE DATA ENGINE ---
@st.cache_data(ttl=3600)
def get_alpha_data(symbol):
    try:
        # Use TIME_SERIES_DAILY (Standard) instead of ADJUSTED for better free-tier compatibility
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url)
        data = r.json()
        
        # 1. Check for Rate Limit Message
        if "Note" in data:
            return "API Limit Reached. Wait 1 minute.", None
        
        # 2. Check for Invalid API Key or Ticker
        if "Error Message" in data:
            return "Invalid Ticker or API Key.", None
            
        # 3. Check if the key exists in the response
        if 'Time Series (Daily)' not in data:
            # This will show us what Alpha Vantage actually said
            return f"Alpha Vantage Error: {list(data.keys())}", None
        
        df = pd.DataFrame.from_dict(data['Time Series (Daily)'], orient='index')
        df = df.astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # Map Alpha Vantage names to our dashboard names
        df = df.rename(columns={
            '1. open': 'Open', '2. high': 'High', 
            '3. low': 'Low', '4. close': 'Close', '5. volume': 'Volume'
        })
        return "OK", df
    except Exception as e:
        return str(e), None

status, df = get_alpha_data(ticker)

# --- 3. DASHBOARD RENDERING ---
if status == "OK":
    # --- FLOW CALCULATIONS ---
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['Net_Flow'] = np.where(df['Close'] > df['Close'].shift(1), 
                              df['TP'] * df['Volume'], -df['TP'] * df['Volume'])
    df['Flow_EMA'] = df['Net_Flow'].ewm(span=10).mean()
    
    # VIX Proxy (Volatility)
    df['Vol'] = df['Close'].pct_change().rolling(20).std() * (252**0.5) * 100

    st.title(f"📊 {ticker} Intelligence Terminal")
    
    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Price", f"${df['Close'].iloc[-1]:.2f}")
    c2.metric("Fear (VIX)", f"{df['Vol'].iloc[-1]:.1f}%")
    c3.metric("Daily Flow", f"${df['Net_Flow'].iloc[-1]/1e6:.1f}M")

    # --- CHART 1: PRICE & FLOWS ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price", line=dict(color="white")), secondary_y=False)
    
    recent = df.tail(40)
    fig.add_trace(go.Bar(x=recent.index, y=recent['Net_Flow'], name="Flow", 
                         marker_color=np.where(recent['Net_Flow']>0, '#26a69a', '#ef5350'), opacity=0.4), secondary_y=True)
    
    fig.add_trace(go.Scatter(x=recent.index, y=recent['Flow_EMA'], name="Flow Trend", line=dict(color="#00fbff")), secondary_y=True)
    fig.update_layout(template="plotly_dark", height=500)
    st.plotly_chart(fig, use_container_width=True)

    # --- CHART 2: FEAR ---
    st.subheader("🔥 Volatility Gauge")
    st.area_chart(df['Vol'])

elif status == "LIMIT":
    st.warning("⚠️ Alpha Vantage Free Limit Reached (25 requests/day). Please wait a minute or upgrade.")
else:
    st.error(f"Error: {status}")
