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

st.set_page_config(page_title="High-Certainty Terminal", layout="wide")
ticker = st.sidebar.text_input("Enter Ticker", "HIMS").upper()

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=3600)
def get_full_market_data(symbol):
    try:
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url).json()
        if "Note" in r: return "LIMIT", None, None
        if "Error Message" in r: return "INVALID", None, None
        
        df = pd.DataFrame.from_dict(r['Time Series (Daily)'], orient='index').astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().rename(columns={'1. open':'Open','2. high':'High','3. low':'Low','4. close':'Close','5. volume':'Volume'})
        
        time.sleep(1.5) # API Breathing Room
        
        url_spy = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=SPY&apikey={AV_KEY}'
        r_spy = requests.get(url_spy).json()
        spy = pd.DataFrame.from_dict(r_spy['Time Series (Daily)'], orient='index').astype(float)
        spy = spy.sort_index()['4. close']
        spy.index = pd.to_datetime(spy.index)

        common = df.index.intersection(spy.index)
        return "OK", df.loc[common], spy.loc[common]
    except Exception as e:
        return str(e), None, None

status, df, spy_price = get_full_market_data(ticker)

# --- 3. DASHBOARD LOGIC ---
if status == "OK":
    # --- UPDATED MATH (Faster Lookbacks) ---
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['Net_Flow'] = np.where(df['Close'] > df['Close'].shift(1), df['TP'] * df['Volume'], -df['TP'] * df['Volume'])
    df['Flow_EMA'] = df['Net_Flow'].ewm(span=10).mean()
    df['RS_Line'] = (df['Close'] / df['Close'].iloc[0]) / (spy_price / spy_price.iloc[0])
    df['RVOL'] = df['Volume'] / df['Volume'].rolling(20).mean()
    df['Vol'] = df['Close'].pct_change().rolling(20).std() * (252**0.5) * 100
    
    # Threshold reduced to 20 days so the red line shows up faster
    df['Threshold'] = df['Vol'].rolling(20).mean() + (1.5 * df['Vol'].rolling(20).std())

    # IDENTIFY BUY SIGNALS (Whale Buying Footprints)
    # RVOL > 1.2 and Net Flow is Positive
    df['Whale_Buy'] = np.where((df['Net_Flow'] > 0) & (df['RVOL'] > 1.2), df['Close'], np.nan)

    st.title(f"🚀 {ticker} Conviction Terminal")
    
    # --- TOP METRICS ---
    flow_val = df['Net_Flow'].iloc[-1]
    flow_disp = f"${flow_val/1e9:.1f}B" if abs(flow_val) >= 1e9 else f"${flow_val/1e6:.1f}M"
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Price", f"${df['Close'].iloc[-1]:.2f}")
    m2.metric("Whale Activity (RVOL)", f"{df['RVOL'].iloc[-1]:.1f}x")
    m3.metric("Fear Level", f"{df['Vol'].iloc[-1]:.1f}%")
    m4.metric("Inst. Flow", flow_disp)

    # --- CHART 1: FLOW & SIGNALS ---
    st.subheader("💳 Institutional Flow & Whale Markers")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # The Main Price Line
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price", 
                             line=dict(color="#003366", width=3)), secondary_y=False)
    
    # NEW: Whale Buy Markers (Green Triangles)
    fig.add_trace(go.Scatter(x=df.index, y=df['Whale_Buy'], mode='markers', name='Whale Entry',
                             marker=dict(color='#00ff00', size=12, symbol='triangle-up', 
                             line=dict(width=1, color='black'))), secondary_y=False)
    
    recent = df.tail(60)
    # Net Flow Bars
    fig.add_trace(go.Bar(x=recent.index, y=recent['Net_Flow'], name="Net Flow", 
                         marker_color=np.where(recent['Net_Flow']>0, '#26a69a', '#ef5350'), opacity=0.4), secondary_y=True)
    
    # Flow Trend Line
    fig.add_trace(go.Scatter(x=recent.index, y=recent['Flow_EMA'], name="Flow Trend", 
                             line=dict(color="#007bff", width=2)), secondary_y=True)
    
    fig.update_layout(template="plotly_white", height=500, paper_bgcolor="white", font=dict(color="black"), hovermode="x unified")
    fig.update_yaxes(tickformat="~s", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    # --- CHART 2: FEAR GAUGE ---
    st.subheader("🔥 Dynamic Panic Threshold")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df.index, y=df['Vol'], name="Volatility", fill='tozeroy', line=dict(color="orange")))
    fig2.add_trace(go.Scatter(x=df.index, y=df['Threshold'], name="Panic Line", line=dict(color="red", dash="dash")))
    fig2.update_layout(template="plotly_white", height=300)
    st.plotly_chart(fig2, use_container_width=True)

    # --- VERDICT ---
    st.subheader("🎯 Verdict")
    if not np.isnan(df['Whale_Buy'].iloc[-1]):
        st.success("🏹 **ACTIVE BUY SIGNAL:** A high-volume Whale entry was detected today!")
    elif flow_val > 0:
        st.info("✅ **BULLISH BIAS:** Flow is positive, but waiting for high-volume Whale confirmation.")
    elif flow_val < 0 and df['RVOL'].iloc[-1] > 1.2:
        st.error("🛡️ **SELL SIGNAL:** High-volume institutional exit detected.")
    else:
        st.info("⚖️ **NEUTRAL:** No major institutional activity detected.")

elif status == "LIMIT":
    st.error("🚨 API Limit Reached (25/day).")
else:
    st.error(f"Error: {status}")
