import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- SETUP ---
API_KEY = st.secrets["EOD_KEY"]
st.set_page_config(page_title="Pro ETF Flow Terminal", layout="wide")

ticker = st.sidebar.text_input("Enter Ticker (e.g. SPY.US)", "SPY.US").upper()
if "." not in ticker: ticker += ".US" # EODHD requires the .US suffix

@st.cache_data(ttl=3600)
def get_pro_flow_data(symbol):
    try:
        # 1. Get Historical Price Data
        price_url = f"https://eodhd.com/api/eod/{symbol}?api_token={API_KEY}&fmt=json&period=d"
        p_res = requests.get(price_url).json()
        df_price = pd.DataFrame(p_res).set_index('date')
        df_price.index = pd.to_datetime(df_price.index)

        # 2. Get Historical Shares Outstanding (The Secret Sauce)
        # In 2026, EODHD provides this via the Fundamentals filter
        fund_url = f"https://eodhd.com/api/fundamentals/{symbol}?api_token={API_KEY}&filter=outstandingShares"
        f_res = requests.get(fund_url).json()
        
        # Convert dictionary history to DataFrame
        df_shares = pd.DataFrame.from_dict(f_res, orient='index', columns=['shares'])
        df_shares.index = pd.to_datetime(df_shares.index)
        
        # Merge Price and Shares
        merged = df_price.merge(df_shares, left_index=True, right_index=True, how='left')
        merged['shares'] = merged['shares'].ffill() # Fill gaps between reports
        
        return merged
    except Exception as e:
        st.error(f"Error fetching Pro data: {e}")
        return None

data = get_pro_flow_data(ticker)

if data is not None:
    # --- CALCULATE NET FLOWS ---
    # Flow = Change in Shares * Price
    data['Share_Delta'] = data['shares'].diff()
    data['Net_Flow_USD'] = data['Share_Delta'] * data['close']
    
    # --- DASHBOARD UI ---
    st.title(f"🏛️ {ticker} Institutional Intelligence")
    
    col1, col2 = st.columns(2)
    col1.metric("Current AUM Estimate", f"${(data['shares'].iloc[-1] * data['close'].iloc[-1])/1e9:.2f}B")
    
    # --- CHART: THE FLOWS ---
    st.subheader("Institutional Net Flow (Creation/Redemption)")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Price Line
    fig.add_trace(go.Scatter(x=data.index, y=data['close'], name="Price", line=dict(color="white")), secondary_y=False)
    
    # Net Flow Bars (Last 60 Days)
    recent = data.tail(60)
    fig.add_trace(go.Bar(
        x=recent.index, 
        y=recent['Net_Flow_USD'],
        name="Net Capital Flow ($)",
        marker_color=np.where(recent['Net_Flow_USD'] >= 0, '#26a69a', '#ef5350')
    ), secondary_y=True)
    
    fig.update_layout(template="plotly_dark", height=600)
    st.plotly_chart(fig, use_container_width=True)

    # --- FEAR GAUGE ---
    st.subheader("🔥 Volatility (Fear)")
    data['Vol'] = data['close'].pct_change().rolling(20).std() * (252**0.5) * 100
    st.line_chart(data['Vol'])

else:
    st.warning("Enter your API Key and a valid ticker to see institutional flows.")
