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
    st.error("Missing 'AV_KEY' in Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="ETF Sentiment Terminal", layout="wide")
ticker = st.sidebar.text_input("Enter Ticker", "SPY").upper()

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=3600)
def get_alpha_data(symbol):
    try:
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url)
        data = r.json()
        if "Note" in data: return "LIMIT", None
        if "Error Message" in data: return "INVALID", None
        
        df = pd.DataFrame.from_dict(data['Time Series (Daily)'], orient='index')
        df = df.astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().rename(columns={
            '1. open': 'Open', '2. high': 'High', 
            '3. low': 'Low', '4. close': 'Close', '5. volume': 'Volume'
        })
        return "OK", df
    except Exception as e:
        return str(e), None

status, df = get_alpha_data(ticker)

# --- 3. DASHBOARD ---
if status == "OK":
    # --- MATH ---
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['Net_Flow'] = np.where(df['Close'] > df['Close'].shift(1), 
                              df['TP'] * df['Volume'], -df['TP'] * df['Volume'])
    df['Flow_EMA'] = df['Net_Flow'].ewm(span=10).mean()
    df['Vol'] = df['Close'].pct_change().rolling(20).std() * (252**0.5) * 100
    df['Threshold'] = df['Vol'].rolling(60).mean() + (1.5 * df['Vol'].rolling(60).std())

    st.title(f"📈 {ticker} Intelligence Terminal")
    
    # Header Metrics
    flow_val = df['Net_Flow'].iloc[-1]
    flow_disp = f"${flow_val/1e9:.2f}B" if abs(flow_val) >= 1e9 else f"${flow_val/1e6:.1f}M"
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"${df['Close'].iloc[-1]:.2f}")
    c2.metric("Fear Index (VIX)", f"{df['Vol'].iloc[-1]:.1f}%")
    c3.metric("Daily Money Flow", flow_disp)

    # --- CHART 1: FLOW ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price", line=dict(color="#003366", width=3)), secondary_y=False)
    recent = df.tail(60)
    fig.add_trace(go.Bar(x=recent.index, y=recent['Net_Flow'], name="Net Flow", 
                         marker_color=np.where(recent['Net_Flow']>0, '#26a69a', '#ef5350'), opacity=0.5), secondary_y=True)
    fig.add_trace(go.Scatter(x=recent.index, y=recent['Flow_EMA'], name="Flow Trend", line=dict(color="#007bff", width=2)), secondary_y=True)
    
    fig.update_layout(template="plotly_white", height=500, hovermode="x unified", paper_bgcolor="white", plot_bgcolor="white", font=dict(color="black"))
    fig.update_yaxes(tickformat="~s", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    # --- CHART 2: FEAR ---
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df.index, y=df['Vol'], name="Volatility", fill='tozeroy', line=dict(color="orange")))
    fig2.add_trace(go.Scatter(x=df.index, y=df['Threshold'], name="Panic Line", line=dict(color="red", dash="dash")))
    fig2.update_layout(template="plotly_white", height=350, paper_bgcolor="white", plot_bgcolor="white", font=dict(color="black"))
    st.plotly_chart(fig2, use_container_width=True)

    # --- 4. THE MISSING SUMMARY (Fixed & Visible) ---
    st.divider()
    st.subheader("💡 Terminal Summary")
    
    # Get latest values for the alert
    curr_vol = df['Vol'].iloc[-1]
    curr_thresh = df['Threshold'].iloc[-1]
    curr_flow = df['Net_Flow'].iloc[-1]
    
    with st.container(border=True):
        col_a, col_b = st.columns(2)
        
        # Volatility Alert
        if curr_vol > curr_thresh:
            col_a.error(f"⚠️ **VOLATILITY ALERT:** {ticker} is currently in a high-stress state, exceeding its dynamic threshold of {curr_thresh:.1f}%.")
        else:
            col_a.success(f"✅ **STABLE VOLATILITY:** {ticker} is trading within its normal risk range.")
            
        # Money Flow Alert
        if curr_flow > 0:
            col_b.info(f"💰 **BULLISH FLOW:** Institutional money is currently entering {ticker}.")
        else:
            col_b.warning(f"📉 **BEARISH FLOW:** Institutional money is currently exiting {ticker}.")

elif status == "LIMIT":
    st.warning("⚠️ API Limit Reached.")
else:
    st.error(f"Error: {status}")
