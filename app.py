import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. ACCESS SECRETS ---
# Make sure your secret name matches exactly what you put in Streamlit
try:
    API_KEY = st.secrets["EOD_KEY"]
except:
    st.error("Missing 'EOD_KEY' in Streamlit Secrets. Please check your settings.")
    st.stop()

# --- SETUP ---
st.set_page_config(page_title="ETF Command Center", layout="wide")

ticker = st.sidebar.text_input("Enter Ticker (e.g. SPY.US)", "SPY.US").upper()
if "." not in ticker: ticker += ".US"

@st.cache_data(ttl=3600)
def get_master_data(symbol):
    try:
        # A. PRICE DATA
        p_res = requests.get(f"https://eodhd.com/api/eod/{symbol}?api_token={API_KEY}&fmt=json")
        if p_res.status_code != 200: return None, None, None
        df = pd.DataFrame(p_res.json()).set_index('date')
        df.index = pd.to_datetime(df.index)

        # B. INSTITUTIONAL SHARES (Historical)
        # We request the full history of outstanding shares
        f_url = f"https://eodhd.com/api/fundamentals/{symbol}?api_token={API_KEY}&filter=outstandingShares"
        f_res = requests.get(f_url)
        shares_dict = f_res.json() if f_res.status_code == 200 else {}

        # C. OPTIONS DATA (Implied Volatility)
        opt_res = requests.get(f"https://eodhd.com/api/options/{symbol}?api_token={API_KEY}")
        iv_val = None
        if opt_res.status_code == 200:
            opt_data = opt_res.json()
            if 'data' in opt_data and len(opt_data['data']) > 0:
                # Get IV from the first available contract group
                iv_val = opt_data['data'][0].get('impliedVolatility', 0) * 100

        return df, shares_dict, iv_val
    except Exception as e:
        return None, None, None

df, shares, iv = get_master_data(ticker)

if df is not None:
    # --- PROCESS FLOW DATA ---
    # EODHD Shares data usually comes as a list of dicts: [{'date': '...', 'shares': ...}]
    if isinstance(shares, list) and len(shares) > 0:
        df_s = pd.DataFrame(shares).rename(columns={'date': 'Date', 'shares': 'shares_out'})
        df_s['Date'] = pd.to_datetime(df_s['Date'])
        df_s = df_s.set_index('Date')
        
        # Merge with Price and fill the gaps (Shares don't change every single day)
        df = df.merge(df_s, left_index=True, right_index=True, how='left')
        df['shares_out'] = df['shares_out'].ffill()
        
        # Calculate Dollar Flow: Change in Shares * Current Price
        df['Net_Flow'] = df['shares_out'].diff() * df['close']
    else:
        df['Net_Flow'] = 0

    # VIX Proxy (Historical Volatility)
    df['Vol'] = df['close'].pct_change().rolling(20).std() * (252**0.5) * 100
    curr_vol = df['Vol'].iloc[-1]

    # --- UI LAYOUT ---
    st.title(f"🏛️ {ticker} Intelligence Terminal")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Price", f"${df['close'].iloc[-1]:.2f}")
    m2.metric("Fear (VIX)", f"{curr_vol:.1f}%")
    m3.metric("IV (Forward)", f"{iv:.1f}%" if iv else "N/A")
    m4.metric("Market Cap", f"${(df['shares_out'].iloc[-1]*df['close'].iloc[-1])/1e9:.2f}B" if 'shares_out' in df else "N/A")

    # --- CHART 1: PRICE & FLOWS ---
    st.subheader("💳 Institutional Flow (Creation/Redemption)")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Price Line
    fig.add_trace(go.Scatter(x=df.index, y=df['close'], name="Price", line=dict(color="#1f77b4")), secondary_y=False)
    
    # Flow Bars
    recent = df.tail(60)
    if 'Net_Flow' in recent and recent['Net_Flow'].abs().sum() > 0:
        fig.add_trace(go.Bar(
            x=recent.index, y=recent['Net_Flow'], 
            name="Net Flow ($)", 
            marker_color=np.where(recent['Net_Flow'] >= 0, '#26a69a', '#ef5350'),
            opacity=0.6
        ), secondary_y=True)
    
    fig.update_layout(height=450, template="plotly_dark", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # --- CHART 2: THE FEAR GAUGE ---
    st.subheader("🔥 Volatility & Sentiment")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df.index, y=df['Vol'], name="Fear", line=dict(color="orange"), fill='tozeroy'))
    fig2.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="Panic Zone")
    fig2.update_layout(height=350, template="plotly_dark")
    st.plotly_chart(fig2, use_container_width=True)

else:
    st.error("Error: Could not retrieve data. Check your Ticker suffix (e.g., SPY.US) and API Key in Secrets.")
