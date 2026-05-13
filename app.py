import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 1. SETUP & SECRETS ---
try:
    AV_KEY = st.secrets["AV_KEY"]
except:
    st.error("Missing 'AV_KEY' in Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="Whale Conviction Terminal", layout="wide")
ticker = st.sidebar.text_input("Enter Ticker", "HIMS").upper()

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=3600)
def get_market_data(symbol):
    try:
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url).json()
        if "Note" in r: return "LIMIT", None, None
        if 'Time Series (Daily)' not in r: return "ERROR", None, None

        df = pd.DataFrame.from_dict(r['Time Series (Daily)'], orient='index').astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().rename(columns={'1. open':'Open','2. high':'High','3. low':'Low','4. close':'Close','5. volume':'Volume'})
        
        # Simple math for Flow
        df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
        # Flow logic: If price closed higher than yesterday, volume is "Positive Flow"
        df['Net_Flow'] = np.where(df['Close'] > df['Close'].shift(1), df['TP'] * df['Volume'], -df['TP'] * df['Volume'])
        # The Cyan Line Math (Flow Trend)
        df['Flow_EMA'] = df['Net_Flow'].ewm(span=10, adjust=False).mean()
        
        # Whale Detection & Fear Math
        df['RVOL'] = df['Volume'] / df['Volume'].rolling(20).mean()
        df['Vol'] = df['Close'].pct_change().rolling(20).std() * (252**0.5) * 100
        df['Threshold'] = df['Vol'].rolling(20).mean() + (1.5 * df['Vol'].rolling(20).std())
        df['Whale_Buy'] = np.where((df['Net_Flow'] > 0) & (df['RVOL'] > 1.2), df['Close'], np.nan)
        
        return "OK", df, None
    except:
        return "CONNECTION_ERROR", None, None

status, df, _ = get_market_data(ticker)

# --- 3. DASHBOARD RENDER ---
if status == "OK":
    st.title(f"🚀 {ticker} Conviction Terminal")
    
    # METRICS ROW
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Price", f"${df['Close'].iloc[-1]:.2f}")
    m2.metric("Whale Activity (RVOL)", f"{df['RVOL'].iloc[-1]:.1f}x")
    m3.metric("Fear Level", f"{df['Vol'].iloc[-1]:.1f}%")
    m4.metric("Daily Flow", f"${(df['Net_Flow'].iloc[-1]/1e6):.1f}M")

    # --- CHART 1: PRICE & FLOW TREND ---
    st.subheader("💳 Institutional Flow Trend")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Price Line (Primary Axis)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price", line=dict(color="#003366", width=2)), secondary_y=False)
    
    # Whale Markers (Primary Axis)
    fig.add_trace(go.Scatter(x=df.index, y=df['Whale_Buy'], mode='markers', name='Whale Entry', 
                             marker=dict(color='#00ff00', size=12, symbol='triangle-up')), secondary_y=False)
    
    # Flow Trend (Cyan Line - Secondary Axis)
    fig.add_trace(go.Scatter(x=df.index, y=df['Flow_EMA'], name="Flow Trend (Whales)", 
                             line=dict(color="cyan", width=3)), secondary_y=True)
    
    # Net Flow Bars (Secondary Axis)
    recent = df.tail(60)
    fig.add_trace(go.Bar(x=recent.index, y=recent['Net_Flow'], name="Net Flow Bars", 
                         marker_color=np.where(recent['Net_Flow']>0, '#26a69a', '#ef5350'), opacity=0.3), secondary_y=True)
    
    fig.update_layout(template="plotly_white", height=500, showlegend=True, 
                      hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

    # --- CHART 2: FEAR GAUGE ---
    st.subheader("🔥 Dynamic Panic Threshold")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df.index, y=df['Vol'], name="Volatility (Fear)", fill='tozeroy', line=dict(color="orange")))
    fig2.add_trace(go.Scatter(x=df.index, y=df['Threshold'], name="Panic Line", line=dict(color="red", dash="dash")))
    fig2.update_layout(template="plotly_white", height=300)
    st.plotly_chart(fig2, use_container_width=True)

    # --- 4. THE VERDICT BOX ---
    st.divider()
    st.subheader("🎯 Conviction Verdict")
    
    latest_whale = df['Whale_Buy'].iloc[-1]
    latest_flow = df['Net_Flow'].iloc[-1]
    latest_rvol = df['RVOL'].iloc[-1]
    latest_fear = df['Vol'].iloc[-1]

    with st.container(border=True):
        if not np.isnan(latest_whale):
            st.success(f"🏹 **STRONG BUY:** High-volume Whale entry ({latest_rvol:.1f}x volume) detected at ${df['Close'].iloc[-1]:.2f}.")
        elif latest_flow > 0 and latest_fear < 80:
            st.info("✅ **BULLISH BIAS:** Institutional flow is positive and fear is manageable. Steady accumulation likely.")
        elif latest_fear > 90:
            st.warning("⚠️ **EXTREME VOLATILITY:** Fear is at 95%+. Even if Whales are buying, expect massive price swings. Proceed with tight stops.")
        elif latest_flow < 0:
            st.error("🛡️ **BEARISH ALERT:** Money is flowing out of the stock on high volume. Whales are likely distributing.")
        else:
            st.write("⚖️ **NEUTRAL:** Normal trading day. No significant Whale footprints detected.")

elif status == "LIMIT":
    st.error("🚨 API Limit Reached. Please wait a moment or check your key.")
else:
    st.error("⚠️ Ticker not found or connection error.")
