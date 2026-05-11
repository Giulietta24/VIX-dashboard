import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Set Page Config
st.set_page_config(page_title="2026 ETF Sentiment Dashboard", layout="wide")

st.title("📊 2026 ETF Sentiment & Flow Tracker")
st.markdown("Track **Sentiment (Volatility)** and **Capital Flows** for free.")

# 1. Sidebar Configuration
ticker = st.sidebar.text_input("Enter ETF Ticker (e.g., PAVE, SMH, ICLN)", "PAVE").upper()
period = st.sidebar.selectbox("Analysis Period", ["1mo", "3mo", "6mo", "1y"], index=1)

@st.cache_data(ttl=3600)
def get_etf_data(symbol):
    try:
        etf = yf.Ticker(symbol)
        hist = etf.history(period="1y")
        info = etf.info
        return etf, hist, info
    except:
        return None, None, None

etf_obj, hist, info = get_etf_data(ticker)

if hist is not None and not hist.empty:
    # --- CALCULATIONS ---
    # 1. Fear Index (Historical Volatility)
    hist['Returns'] = hist['Close'].pct_change()
    vol = hist['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
    current_vol = vol.iloc[-1]
    
    # 2. Daily Fund Flow Proxy
    # Formula: (Today's Shares - Yesterday's Shares) * Close Price
    shares_outstanding = info.get('sharesOutstanding', 0)
    # Note: Free APIs update 'shares' daily, so we look for jumps in market cap vs price
    mkt_cap = info.get('totalAssets', 0) # Using Assets as proxy for ETF size
    
    # --- UI LAYOUT ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Current Price", f"${hist['Close'].iloc[-1]:.2f}", f"{hist['Returns'].iloc[-1]*100:.2f}%")
    col2.metric("Fear Index (Vol)", f"{current_vol:.1f}%", "High" if current_vol > 25 else "Stable")
    col3.metric("Total Assets (Est)", f"${mkt_cap/1e9:.2f}B")

    # --- CHARTS ---
    st.subheader(f"{ticker} Momentum & Fear Gauge")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Price", line=dict(color="#1f77b4")))
    fig.add_trace(go.Scatter(x=hist.index, y=vol, name="Fear (Vol)", line=dict(color="red", dash='dot'), yaxis="y2"))
    
    fig.update_layout(
        yaxis=dict(title="Price ($)"),
        yaxis2=dict(title="Volatility %", overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- SENTIMENT ANALYSIS ---
    st.subheader("Signal Intelligence")
    if current_vol > 30 and hist['Returns'].iloc[-5:].sum() < -0.05:
        st.error("🚨 PANIC DETECTED: High Volatility + Price Drop. Potential Capitulation.")
    elif current_vol < 15 and hist['Returns'].iloc[-5:].sum() > 0.05:
        st.warning("⚠️ GREED DETECTED: Low Volatility + Price Spike. Possible Overbought.")
    else:
        st.success("✅ STABLE: Asset is moving within normal ranges.")

else:
    st.error("Ticker not found. Please enter a valid ETF symbol.")