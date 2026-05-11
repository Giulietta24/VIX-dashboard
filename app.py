import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- Page Setup ---
st.set_page_config(page_title="2026 ETF Intelligence", layout="wide")
st.title("📊 2026 ETF Capital Flow & Fear Tracker")

# 1. DEFINE TICKER FIRST (Fixes NameError)
ticker = st.sidebar.text_input("Enter Ticker (e.g., PAVE, SMH, XLK)", "PAVE").upper()

# --- FUNCTIONS ---
@st.cache_data(ttl=3600)
def get_market_data(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1y")
        return hist, t.info
    except:
        return None, None

@st.cache_data(ttl=3600)
def get_implied_vol(symbol):
    try:
        t = yf.Ticker(symbol)
        expiries = t.options
        if not expiries: return None
        
        # Pick expiry approx 30 days out
        target_expiry = expiries[0]
        for date in expiries:
            days_out = (pd.to_datetime(date) - pd.Timestamp.today()).days
            if days_out > 20:
                target_expiry = date
                break
        
        opt = t.option_chain(target_expiry)
        if opt.calls.empty or opt.puts.empty: return None
        
        calls_iv = opt.calls['impliedVolatility'].median()
        puts_iv = opt.puts['impliedVolatility'].median()
        return (calls_iv + puts_iv) / 2 * 100
    except:
        return None

# --- EXECUTION ---
hist, info = get_market_data(ticker)
ticker_iv = get_implied_vol(ticker)

if hist is not None and not hist.empty:
    # Calculate Historical Vol (VIX Proxy)
    hist['Returns'] = np.log(hist['Close'] / hist['Close'].shift(1))
    hist['VIX_Proxy'] = hist['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
    current_vix = hist['VIX_Proxy'].iloc[-1]

    # --- TOP METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Price", f"${hist['Close'].iloc[-1]:.2f}")
    m2.metric("Shares Out", f"{info.get('sharesOutstanding', 0):,}")
    m3.metric("Fear (Hist)", f"{current_vix:.1f}%")
    
    if ticker_iv:
        m4.metric("IV (Forward)", f"{ticker_iv:.1f}%")
    else:
        m4.metric("IV (Forward)", "N/A")

    # --- CHART 1: PRICE & FLOWS ---
    st.subheader("💳 Price vs. Capital Flow")
    if os.path.exists('flow_history.csv'):
        flow_df = pd.read_csv('flow_history.csv')
        flow_df['Date'] = pd.to_datetime(flow_df['Date'])
        flow_df['Daily_Change'] = flow_df['Shares'].diff()

        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Price", line=dict(color="#1f77b4")), secondary_y=False)
        fig1.add_trace(go.Bar(x=flow_df['Date'], y=flow_df['Daily_Change'], name="Share Flow", marker_color="green", opacity=0.4), secondary_y=True)
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.line_chart(hist['Close'])
        st.info("Recording daily flows... check back tomorrow for bars.")

    # --- CHART 2: THE VIX GAUGE ---
    st.subheader("🔥 Volatility & Sentiment")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=hist.index, y=hist['VIX_Proxy'], name="Historical Vol", line=dict(color="orange")))
    fig2.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="Panic Zone")
    st.plotly_chart(fig2, use_container_width=True)

    # --- ALPHA ALERTS ---
    if ticker_iv and current_vix:
        if ticker_iv > current_vix + 10:
            st.warning(f"⚠️ **High IV Skew:** Option traders are pricing in a major move soon.")
        elif current_vix > 35:
            st.error("🚨 **Panic detected:** Potential capitulation/bottoming area.")

else:
    st.error("Ticker data unavailable.")
