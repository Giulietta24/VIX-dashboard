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

st.set_page_config(page_title="ETF Sentiment Terminal", layout="wide")

# Sidebar for Ticker Input
ticker = st.sidebar.text_input("Enter Ticker (e.g., SPY, PAVE, SMH)", "SPY").upper()

# --- 2. DATA ENGINE (Alpha Vantage) ---
@st.cache_data(ttl=3600)
def get_alpha_data(symbol):
    try:
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url)
        data = r.json()
        
        if "Note" in data:
            return "API Limit Reached. Wait 1 minute.", None
        if "Error Message" in data:
            return "Invalid Ticker or API Key.", None
        if 'Time Series (Daily)' not in data:
            return "Unexpected Data Format from API.", None
        
        df = pd.DataFrame.from_dict(data['Time Series (Daily)'], orient='index')
        df = df.astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # Mapping Column Names
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
    # --- FLOW & VOLATILITY CALCULATIONS ---
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    # Synthetic Capital Flow
    df['Net_Flow'] = np.where(df['Close'] > df['Close'].shift(1), 
                              df['TP'] * df['Volume'], -df['TP'] * df['Volume'])
    df['Flow_EMA'] = df['Net_Flow'].ewm(span=10).mean()
    
    # VIX Proxy (20-day Annualized Volatility)
    df['Vol'] = df['Close'].pct_change().rolling(20).std() * (252**0.5) * 100

    st.title(f"📊 {ticker} Intelligence Terminal")
    
    # Header Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"${df['Close'].iloc[-1]:.2f}")
    c2.metric("Market Fear (VIX)", f"{df['Vol'].iloc[-1]:.1f}%")
    c3.metric("Daily Flow ($)", f"${df['Net_Flow'].iloc[-1]/1e6:.1f}M")

    # --- CHART 1: PRICE vs CAPITAL FLOW ---
    st.subheader("💳 Institutional Flow & Price Action")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Price Line (White)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price", line=dict(color="white", width=2)), secondary_y=False)
    
    # Flow Bars (Green/Red)
    recent = df.tail(60)
    fig.add_trace(go.Bar(
        x=recent.index, y=recent['Net_Flow'], name="Net Flow", 
        marker_color=np.where(recent['Net_Flow']>0, '#26a69a', '#ef5350'), 
        opacity=0.4
    ), secondary_y=True)
    
    # Flow Trend Line (Cyan)
    fig.add_trace(go.Scatter(x=recent.index, y=recent['Flow_EMA'], name="Flow Trend", line=dict(color="#00fbff", width=2)), secondary_y=True)
    
    fig.update_layout(template="plotly_dark", height=500, hovermode="x unified", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

    # --- CHART 2: FEAR GAUGE (The Restored Logic) ---
    st.subheader("🔥 Volatility & Sentiment Signal")
    
    fig2 = go.Figure()
    
    # The Orange Fear Area
    fig2.add_trace(go.Scatter(
        x=df.index, 
        y=df['Vol'], 
        name="Volatility", 
        fill='tozeroy', 
        line=dict(color="orange", width=2)
    ))

    # The Red Panic Line (Threshold)
    fig2.add_hline(
        y=30, 
        line_dash="dash", 
        line_color="red", 
        annotation_text="Panic Zone (30%)", 
        annotation_position="top right"
    )

    fig2.update_layout(
        template="plotly_dark", 
        height=350, 
        yaxis_title="Volatility %",
        xaxis_title="Date",
        margin=dict(l=20, r=20, t=20, b=20)
    )
    
    st.plotly_chart(fig2, use_container_width=True)

    # --- ALPHA ALERTS ---
    if df['Vol'].iloc[-1] > 30:
        st.error(f"🚨 **Extreme Fear:** {ticker} has entered the Panic Zone.")
    elif df['Vol'].iloc[-1] < 12:
        st.info(f"⚖️ **Complacency:** Market volatility for {ticker} is exceptionally low.")

elif status == "LIMIT":
    st.warning("⚠️ Alpha Vantage Free Limit Reached. Please wait a minute before refreshing.")
else:
    st.error(f"System Error: {status}")
