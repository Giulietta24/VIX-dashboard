import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Configuration ---
st.set_page_config(page_title="2026 ETF Command Center", layout="wide")
st.title("📊 2026 ETF Money Flow & Fear Dashboard")

# 1. Sidebar Input
ticker = st.sidebar.text_input("Enter ETF Ticker", "PAVE").upper()
lookback = st.sidebar.slider("Days to Analyze", 5, 60, 20)

@st.cache_data(ttl=3600)
def get_all_data(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1y")
        # Get Implied Vol (IV)
        expiries = t.options
        iv = None
        if expiries:
            opt = t.option_chain(expiries[0])
            iv = (opt.calls['impliedVolatility'].median() + opt.puts['impliedVolatility'].median()) / 2 * 100
        return hist, t.info, iv
    except:
        return None, None, None

hist, info, iv = get_all_data(ticker)

if hist is not None and not hist.empty:
    # --- CALCULATION: DYNAMIC MONEY FLOW ---
    # We calculate 'Typical Price' to determine money direction
    hist['Typical_Price'] = (hist['High'] + hist['Low'] + hist['Close']) / 3
    hist['Money_Flow'] = hist['Typical_Price'] * hist['Volume']
    
    # Direction: If today's typical price > yesterday's, it's an INFLOW
    hist['Flow_Dir'] = np.where(hist['Typical_Price'] > hist['Typical_Price'].shift(1), 
                                hist['Money_Flow'], -hist['Money_Flow'])
    
    # Historical Volatility (The Proxy VIX)
    hist['Returns'] = np.log(hist['Close'] / hist['Close'].shift(1))
    hist['HV'] = hist['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
    
    # --- ROW 1: METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Price", f"${hist['Close'].iloc[-1]:.2f}")
    m2.metric("Assets (AUM)", f"${info.get('totalAssets', 0)/1e9:.2f}B")
    m3.metric("Fear (Hist Vol)", f"{hist['HV'].iloc[-1]:.1f}%")
    m4.metric("IV (Forward)", f"{iv:.1f}%" if iv else "N/A")

    # --- ROW 2: PRICE & FLOW CHART ---
    st.subheader(f"📈 {ticker} Price & Net Money Flow")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Price Line
    fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Price", line=dict(color="#1f77b4", width=3)), secondary_y=False)
    
    # Flow Bars (Limited to user selection)
    recent = hist.tail(lookback)
    fig.add_trace(go.Bar(
        x=recent.index, 
        y=recent['Flow_Dir'],
        name="Net Money Flow",
        marker_color=np.where(recent['Flow_Dir'] >= 0, '#26a69a', '#ef5350'),
        opacity=0.6
    ), secondary_y=True)
    
    fig.update_layout(height=500, legend=dict(orientation="h", y=1.1, x=1))
    st.plotly_chart(fig, use_container_width=True)

    # --- ROW 3: FEAR GAUGE (VIX) ---
    st.subheader("🔥 Volatility & Sentiment Signals")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=hist.index, y=hist['HV'], name="Fear Index", fill='tozeroy', line=dict(color="orange")))
    fig2.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="PANIC ZONE")
    st.plotly_chart(fig2, use_container_width=True)

    # --- AI ADVISORY ---
    st.info(f"**Current Status for {ticker}:** " + 
            ("Accumulation (Money entering)" if hist['Flow_Dir'].iloc[-1] > 0 else "Distribution (Money exiting)") + 
            " | " + 
            ("High Risk/Volatility" if hist['HV'].iloc[-1] > 30 else "Stable/Low Volatility"))

else:
    st.error("Invalid Ticker. Please try again.")
