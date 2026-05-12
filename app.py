import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

# --- 1. SETUP & THEME ---
st.set_page_config(page_title="2026 ETF Intelligence", layout="wide")
st.title("📊 ETF Capital Flow & Fear Tracker")

# Sidebar for Ticker Input
ticker = st.sidebar.text_input("Enter Ticker (e.g., PAVE, SMH, SPY)", "PAVE").upper()

# --- 2. DATA ENGINE (With Rate Limit Protection) ---
@st.cache_data(ttl=86400) # Cache for 24 hours to avoid Yahoo Rate Limits
def get_clean_data(symbol):
    try:
        # Create a session to look like a browser
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        
        t = yf.Ticker(symbol, session=session)
        hist = t.history(period="1y")
        
        if hist.empty:
            return None, None, None
            
        # Get Implied Volatility (IV)
        iv = None
        if t.options:
            try:
                opt = t.option_chain(t.options[0])
                iv = (opt.calls['impliedVolatility'].median() + opt.puts['impliedVolatility'].median()) / 2 * 100
            except:
                iv = None
                
        return hist, t.info, iv
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
        return None, None, None

# --- 3. EXECUTION ---
hist, info, iv = get_clean_data(ticker)

if hist is not None:
    # --- CALCULATE FLOWS & VOLATILITY ---
    # Typical Price Money Flow Logic
    hist['TP'] = (hist['High'] + hist['Low'] + hist['Close']) / 3
    hist['Flow'] = hist['TP'] * hist['Volume']
    hist['Net_Flow'] = np.where(hist['Close'] > hist['Close'].shift(1), hist['Flow'], -hist['Flow'])
    
    # Smooth Trend Line (The "Institutional Trend")
    hist['Flow_Trend'] = hist['Net_Flow'].ewm(span=10).mean()

    # VIX Proxy (Historical Volatility)
    hist['Returns'] = np.log(hist['Close'] / hist['Close'].shift(1))
    hist['VIX_Proxy'] = hist['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
    curr_vix = hist['VIX_Proxy'].iloc[-1]

    # --- ROW 1: TOP METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Price", f"${hist['Close'].iloc[-1]:.2f}")
    m2.metric("Fear (VIX)", f"{curr_vix:.1f}%")
    m3.metric("Option IV", f"{iv:.1f}%" if iv else "N/A")
    m4.metric("Assets (AUM)", f"${info.get('totalAssets', 0)/1e9:.2f}B")

    # --- ROW 2: MAIN CHART ---
    st.subheader(f"📈 {ticker} Price vs. Net Capital Flow")
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Price Line
    fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Price", line=dict(color="#1f77b4", width=3)), secondary_y=False)

    # Net Flow Bars (Last 50 Days)
    recent = hist.tail(50)
    fig.add_trace(go.Bar(
        x=recent.index, 
        y=recent['Net_Flow'],
        name="Net Money Flow",
        marker_color=np.where(recent['Net_Flow'] >= 0, '#26a69a', '#ef5350'),
        opacity=0.4
    ), secondary_y=True)

    # Flow Trend Line
    fig.add_trace(go.Scatter(
        x=recent.index, y=recent['Flow_Trend'], 
        name="Flow Trend", 
        line=dict(color="#00fbff", width=2)
    ), secondary_y=True)

    fig.update_layout(height=550, template="plotly_dark", hovermode="x unified", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

    # --- ROW 3: VOLATILITY GAUGE ---
    st.subheader("🔥 Volatility & Fear Signal")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=hist.index, y=hist['VIX_Proxy'], name="VIX Proxy", line=dict(color="orange"), fill='tozeroy'))
    fig2.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="Panic Zone")
    fig2.update_layout(height=350, template="plotly_dark")
    st.plotly_chart(fig2, use_container_width=True)

    # --- ALPHA ALERTS ---
    if iv and iv > curr_vix + 10:
        st.warning(f"⚠️ **High IV Skew:** Option traders are pricing in a major move soon for {ticker}.")
    if curr_vix > 30:
        st.error(f"🚨 **Panic Zone:** {ticker} is experiencing extreme volatility.")

else:
    st.error("No data found for this ticker. Try SPY, PAVE, or SMH.")
    st.info("If you see a 'Rate Limit' error, wait a few minutes and try again—Streamlit Cloud IPs are shared.")
