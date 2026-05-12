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
    st.error("Missing 'AV_KEY' in Streamlit Secrets. Please check your settings.")
    st.stop()

st.set_page_config(page_title="2026 Sentiment Terminal", layout="wide")

# Sidebar for Ticker Input
ticker = st.sidebar.text_input("Enter Ticker (e.g., SPY, NVDA, PAVE)", "SPY").upper()

# --- 2. DATA ENGINE (Alpha Vantage) ---
@st.cache_data(ttl=3600)
def get_alpha_data(symbol):
    try:
        # Using TIME_SERIES_DAILY for maximum stability
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url)
        data = r.json()
        
        # Check for API Limits (Free tier is 25 calls/day)
        if "Note" in data:
            return "LIMIT", None
        if "Error Message" in data:
            return "INVALID", None
        if 'Time Series (Daily)' not in data:
            return "DATA_ERROR", None
        
        df = pd.DataFrame.from_dict(data['Time Series (Daily)'], orient='index')
        df = df.astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # Map Columns to standard names
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
    # --- CALCULATIONS ---
    # A. Money Flow (Typical Price * Volume)
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['Net_Flow'] = np.where(df['Close'] > df['Close'].shift(1), 
                              df['TP'] * df['Volume'], -df['TP'] * df['Volume'])
    df['Flow_EMA'] = df['Net_Flow'].ewm(span=10).mean()
    
    # B. Dynamic Volatility (The Fear Gauge)
    df['Vol'] = df['Close'].pct_change().rolling(20).std() * (252**0.5) * 100
    
    # C. Dynamic Threshold (1.5 Sigma Logic)
    df['Vol_Mean'] = df['Vol'].rolling(60).mean()
    df['Vol_Std'] = df['Vol'].rolling(60).std()
    df['Dynamic_Threshold'] = df['Vol_Mean'] + (1.5 * df['Vol_Std'])

    st.title(f"📊 {ticker} Intelligence Terminal")
    
    # Top Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"${df['Close'].iloc[-1]:.2f}")
    c2.metric("Fear Index (VIX)", f"{df['Vol'].iloc[-1]:.1f}%")
    c3.metric("Daily Money Flow", f"${df['Net_Flow'].iloc[-1]/1e6:.1f}M")

    # --- CHART 1: PRICE & CAPITAL FLOW ---
    st.subheader("💳 Institutional Sentiment & Price Action")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Price line
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price", line=dict(color="white", width=2)), secondary_y=False)
    
    # Flow bars (Last 60 Days)
    recent = df.tail(60)
    fig.add_trace(go.Bar(
        x=recent.index, y=recent['Net_Flow'], name="Net Flow", 
        marker_color=np.where(recent['Net_Flow']>0, '#26a69a', '#ef5350'), opacity=0.4
    ), secondary_y=True)
    
    # Flow Trend (Cyan)
    fig.add_trace(go.Scatter(x=recent.index, y=recent['Flow_EMA'], name="Flow Trend", line=dict(color="#00fbff", width=2)), secondary_y=True)
    
    fig.update_layout(template="plotly_dark", height=500, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # --- CHART 2: DYNAMIC FEAR GAUGE ---
    st.subheader(f"🔥 {ticker} Dynamic Panic Threshold")
    
    fig2 = go.Figure()
    # Orange Vol Area
    fig2.add_trace(go.Scatter(x=df.index, y=df['Vol'], name="Volatility", fill='tozeroy', line=dict(color="orange", width=2)))
    # Dynamic Red Dash Line
    fig2.add_trace(go.Scatter(x=df.index, y=df['Dynamic_Threshold'], name="Panic Threshold", line=dict(color="red", width=2, dash="dash")))

    fig2.update_layout(template="plotly_dark", height=350, margin=dict(l=20, r=20, t=20, b=20), legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig2, use_container_width=True)

    # Smart Alerts
    if df['Vol'].iloc[-1] > df['Dynamic_Threshold'].iloc[-1]:
        st.error(f"🚨 **ABNORMAL VOLATILITY:** {ticker} has pierced its panic threshold. High risk detected.")
    else:
        st.success(f"✅ **NORMAL RANGE:** {ticker} is trading within its typical volatility bounds.")

elif status == "LIMIT":
    st.warning("⚠️ Alpha Vantage Daily Limit Reached (25 calls/day). Please wait until tomorrow or upgrade your key.")
elif status == "INVALID":
    st.error("❌ Invalid Ticker. Please check your spelling (e.g., AAPL instead of AAPL.US).")
else:
    st.error(f"System Error: {status}")
