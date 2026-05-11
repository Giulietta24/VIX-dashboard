import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

st.set_page_config(page_title="2026 ETF Flow Dashboard", layout="wide")

st.title("📊 2026 ETF Capital Flow & Fear Tracker")

# Sidebar for Ticker
ticker = st.sidebar.text_input("Enter ETF Ticker", "PAVE").upper()

@st.cache_data(ttl=3600)
def get_etf_data(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1y")
        # We cache the 'info' dict to avoid UnserializableReturnValueError
        info = t.info
        return hist, info
    except:
        return None, None

hist, info = get_etf_data(ticker)

if hist is not None and not hist.empty:
    # --- METRICS ---
    shares_now = info.get('sharesOutstanding', 0)
    aum = info.get('totalAssets', 0)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Current Price", f"${hist['Close'].iloc[-1]:.2f}")
    col2.metric("Shares Outstanding", f"{shares_now:,}")
    col3.metric("Total AUM", f"${aum/1e9:.2f}B")

    # --- FUND FLOWS (SHARES OUTSTANDING) ---
    st.subheader("💳 Daily Capital Flow History")
    
    if os.path.exists('flow_history.csv'):
        # 1. Load the data recorded by your GitHub Action
        flow_df = pd.read_csv('flow_history.csv')
        flow_df['Date'] = pd.to_datetime(flow_df['Date'])
        
        # 2. Calculate daily change (The Flow)
        flow_df['Daily_Change'] = flow_df['Shares'].diff()
        
        # 3. Plot the flows
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=flow_df['Date'], 
            y=flow_df['Daily_Change'],
            marker_color=np.where(flow_df['Daily_Change'] >= 0, 'green', 'red'),
            name="Net Share Flow"
        ))
        fig.update_layout(title="Daily Inflows/Outflows (via Share Creation)", yaxis_title="Shares Delta")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("🕒 **History Recording in Progress.** Once your GitHub Action runs for the first time, your daily Inflow/Outflow chart will appear here.")
        
    # --- FEAR GAUGE (VOLATILITY) ---
    st.subheader("🔥 Fear Index (Volatility)")
    hist['Returns'] = hist['Close'].pct_change()
    vol = hist['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
    
    st.line_chart(vol)
    st.caption("High Volatility (>30%) usually indicates panic and possible bottoming.")

else:
    st.error("Please enter a valid ticker.")
