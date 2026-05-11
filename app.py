import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# Set Page Config
st.set_page_config(page_title="2026 ETF Flow Dashboard", layout="wide")

st.title("📊 2026 ETF Capital Flow & Fear Tracker")
st.markdown("Monitoring **Institutional Creation/Redemption** and **Market Volatility**.")

# Sidebar for User Input
ticker = st.sidebar.text_input("Enter ETF Ticker", "PAVE").upper()

# --- FIX: CACHING RAW DATA ONLY ---
@st.cache_data(ttl=3600)
def get_clean_data(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1y")
        # Return only serializable data (DataFrame and Dict)
        return hist, t.info
    except:
        return None, None

hist, info = get_clean_data(ticker)

if hist is not None and not hist.empty:
    # --- CALCULATIONS ---
    shares_now = info.get('sharesOutstanding', 0)
    aum = info.get('totalAssets', 0)
    curr_price = hist['Close'].iloc[-1]
    
    # Fear Index (20-day Volatility)
    hist['Returns'] = hist['Close'].pct_change()
    vol = hist['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
    curr_vol = vol.iloc[-1]

    # --- TOP METRICS ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Current Price", f"${curr_price:.2f}", f"{hist['Returns'].iloc[-1]*100:.2f}%")
    col2.metric("Shares Outstanding", f"{shares_now:,}")
    col3.metric("Total AUM", f"${aum/1e9:.2f}B")

    # --- THE DUAL-AXIS FLOW CHART ---
    st.subheader(f"📈 {ticker} Price vs. Share Flow History")
    
    if os.path.exists('flow_history.csv'):
        flow_df = pd.read_csv('flow_history.csv')
        flow_df['Date'] = pd.to_datetime(flow_df['Date'])
        flow_df['Daily_Change'] = flow_df['Shares'].diff()

        # Create Figure with Secondary Y-Axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # 1. Price Line (Primary Axis)
        fig.add_trace(
            go.Scatter(x=hist.index, y=hist['Close'], name="Price ($)", line=dict(color="#1f77b4", width=3)),
            secondary_y=False,
        )

        # 2. Share Flow Bars (Secondary Axis)
        recent_flows = flow_df.tail(60) # Show last 2 months of flow
        fig.add_trace(
            go.Bar(
                x=recent_flows['Date'], 
                y=recent_flows['Daily_Change'],
                name="Share Creation/Redemption",
                marker_color=np.where(recent_flows['Daily_Change'] >= 0, '#26a69a', '#ef5350'),
                opacity=0.5
            ),
            secondary_y=True,
        )

        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=30, b=0),
            height=500
        )
        fig.update_yaxes(title_text="Price ($)", secondary_y=False)
        fig.update_yaxes(title_text="Share Delta", secondary_y=True)
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("🕒 **Awaiting First Data Point.** Once your GitHub Action runs tonight, the daily Flow bars will appear under the price line.")
        st.line_chart(hist['Close'])

    # --- SIGNAL INTELLIGENCE ---
    st.subheader("🤖 Alpha Intelligence Signal")
    s_col1, s_col2 = st.columns(2)
    
    with s_col1:
        st.write("**Volatility Status:**")
        if curr_vol > 30:
            st.error(f"HIGH FEAR ({curr_vol:.1f}%) - Market is panicking.")
        elif curr_vol < 15:
            st.warning(f"COMPLACENCY ({curr_vol:.1f}%) - Market is very calm.")
        else:
            st.success(f"STABLE ({curr_vol:.1f}%) - Normal trading range.")

    with s_col2:
        st.write("**Capital Flow Sentiment:**")
        if 'Daily_Change' in locals() and not recent_flows.empty:
            net_flow = recent_flows['Daily_Change'].sum()
            if net_flow > 0:
                st.success(f"ACCUMULATION - Net {net_flow:,.0f} shares created recently.")
            else:
                st.error(f"DISTRIBUTION - Net {abs(net_flow):,.0f} shares redeemed recently.")
        else:
            st.write("Waiting for history data...")

else:
    st.error("Invalid Ticker. Please verify the symbol on Yahoo Finance.")
