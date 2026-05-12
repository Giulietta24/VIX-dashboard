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
    st.error("Missing 'AV_KEY' in Streamlit Secrets. Please add it as AV_KEY = 'YOUR_KEY'.")
    st.stop()

st.set_page_config(page_title="High-Certainty Terminal", layout="wide")
ticker = st.sidebar.text_input("Enter Ticker (e.g., HIMS, SPY, NVDA)", "HIMS").upper()

# --- 2. DATA ENGINE (With Rate-Limit Protection) ---
@st.cache_data(ttl=3600)
def get_market_data(symbol):
    try:
        # Request 1: Main Ticker
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url).json()
        
        if "Note" in r: return "LIMIT", None, None
        if "Error Message" in r: return "INVALID", None, None
        if 'Time Series (Daily)' not in r: return "REJECTED", None, None

        df = pd.DataFrame.from_dict(r['Time Series (Daily)'], orient='index').astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().rename(columns={'1. open':'Open','2. high':'High','3. low':'Low','4. close':'Close','5. volume':'Volume'})
        
        # MANDATORY DELAY: Free tier keys need a breather between calls
        time.sleep(2) 
        
        # Request 2: SPY Benchmark for Relative Strength
        url_spy = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=SPY&apikey={AV_KEY}'
        r_spy = requests.get(url_spy).json()
        
        if 'Time Series (Daily)' not in r_spy: return "LIMIT", None, None

        spy = pd.DataFrame.from_dict(r_spy['Time Series (Daily)'], orient='index').astype(float)
        spy = spy.sort_index()['4. close']
        spy.index = pd.to_datetime(spy.index)

        # Sync dates
        common = df.index.intersection(spy.index)
        return "OK", df.loc[common], spy.loc[common]
    except Exception as e:
        return f"Error: {str(e)}", None, None

status, df, spy_price = get_market_data(ticker)

# --- 3. THE INTELLIGENCE LAYER ---
if status == "OK":
    # MATH: Flow, Whale Activity, & Volatility
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['Net_Flow'] = np.where(df['Close'] > df['Close'].shift(1), df['TP'] * df['Volume'], -df['TP'] * df['Volume'])
    df['Flow_EMA'] = df['Net_Flow'].ewm(span=10).mean()
    df['RS_Line'] = (df['Close'] / df['Close'].iloc[0]) / (spy_price / spy_price.iloc[0])
    df['RVOL'] = df['Volume'] / df['Volume'].rolling(20).mean()
    df['Vol'] = df['Close'].pct_change().rolling(20).std() * (252**0.5) * 100
    df['Threshold'] = df['Vol'].rolling(20).mean() + (1.5 * df['Vol'].rolling(20).std())

    # WHALE SIGNALS: Positive Flow + High Volume (RVOL > 1.2)
    df['Whale_Buy'] = np.where((df['Net_Flow'] > 0) & (df['RVOL'] > 1.2), df['Close'], np.nan)

    st.title(f"🚀 {ticker} Conviction Terminal")
    
    # METRICS
    flow_val = df['Net_Flow'].iloc[-1]
    flow_disp = f"${flow_val/1e9:.1f}B" if abs(flow_val) >= 1e9 else f"${flow_val/1e6:.1f}M"
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Price", f"${df['Close'].iloc[-1]:.2f}")
    m2.metric("Whale Activity (RVOL)", f"{df['RVOL'].iloc[-1]:.1f}x")
    m3.metric("Fear Level", f"{df['Vol'].iloc[-1]:.1f}%")
    m4.metric("Inst. Flow", flow_disp)

    # CHART 1: FLOW & WHALE MARKERS
    # --- CHART 1: FLOW & SIGNALS ---
st.subheader("💳 Institutional Flow & Whale Markers")
fig = make_subplots(specs=[[{"secondary_y": True}]])

# 1. Main Price Line (Always show)
fig.add_trace(go.Scatter(
    x=df.index, y=df['Close'], 
    name="Price", 
    showlegend=True,  # FORCE LEGEND
    line=dict(color="#003366", width=3)
), secondary_y=False)

# 2. Whale Buy Markers
fig.add_trace(go.Scatter(
    x=df.index, y=df['Whale_Buy'], 
    mode='markers', 
    name='Whale Entry',
    showlegend=True, # FORCE LEGEND
    marker=dict(color='#00ff00', size=12, symbol='triangle-up', 
    line=dict(width=1, color='black'))
), secondary_y=False)

# 3. Put/Call Data (The Checkbox Fix)
# Use a checkbox to toggle visibility
show_pc = st.checkbox("Show Put/Call Flow")

if show_pc:
    # Ensure you have your put_call_data defined earlier
    fig.add_trace(go.Scatter(
        x=df.index, y=df['Put_Call_Flow'], # Replace with your actual column name
        name="Put/Call Flow",
        showlegend=True, # FORCE LEGEND
        line=dict(color="purple", width=2, dash="dot")
    ), secondary_y=True)

# 4. Net Flow Bars
recent = df.tail(60)
fig.add_trace(go.Bar(
    x=recent.index, y=recent['Net_Flow'], 
    name="Net Flow", 
    showlegend=True, # FORCE LEGEND
    marker_color=np.where(recent['Net_Flow']>0, '#26a69a', '#ef5350'), 
    opacity=0.4
), secondary_y=True)

# --- THE LEGEND FIX ---
fig.update_layout(
    template="plotly_white", 
    height=500, 
    showlegend=True, # FORCE THE GLOBAL LEGEND
    legend=dict(
        orientation="h",   # Horizontal legend
        yanchor="bottom",
        y=1.02,            # Place it above the chart
        xanchor="right",
        x=1
    ),
    paper_bgcolor="white", 
    font=dict(color="black"), 
    hovermode="x unified"
)

fig.update_yaxes(tickformat="~s", secondary_y=True)
st.plotly_chart(fig, use_container_width=True)

    # CHART 2: FEAR GAUGE
    st.subheader("🔥 Dynamic Panic Threshold")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df.index, y=df['Vol'], name="Volatility", fill='tozeroy', line=dict(color="orange")))
    fig2.add_trace(go.Scatter(x=df.index, y=df['Threshold'], name="Panic Line", line=dict(color="red", dash="dash")))
    fig2.update_layout(template="plotly_white", height=300, font=dict(color="black"))
    st.plotly_chart(fig2, use_container_width=True)

    # VERDICT BOX
    st.subheader("🎯 Conviction Verdict")
    if not np.isnan(df['Whale_Buy'].iloc[-1]):
        st.success("🏹 **BUY SIGNAL:** High-volume Whale entry detected today.")
    elif flow_val > 0:
        st.info("✅ **BULLISH:** Flow is positive, but waiting for Whale volume.")
    elif flow_val < 0 and df['RVOL'].iloc[-1] > 1.2:
        st.error("🛡️ **SELL SIGNAL:** High-volume Whale exit detected.")
    else:
        st.info("⚖️ **NEUTRAL:** No major institutional activity.")

elif status == "LIMIT":
    st.error("🚨 **API Limit Reached (25 calls/day).** Wait until tomorrow or swap your API key in Secrets.")
elif status == "REJECTED":
    st.warning("⚠️ **API Busy.** Refresh the page in a few seconds.")
else:
    st.error(f"Error: {status}")
