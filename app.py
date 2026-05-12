import streamlit as st  # This MUST be line 1
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. SETUP & SECRETS ---
try:
    AV_KEY = st.secrets["AV_KEY"]
except:
    st.error("Missing 'AV_KEY' in Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="Institutional Intelligence Terminal", layout="wide")
ticker = st.sidebar.text_input("Enter Ticker", "SPY").upper()

# --- 2. THE DATA ENGINE (SMARTER ERROR HANDLING) ---
@st.cache_data(ttl=3600)
def get_full_market_data(symbol):
    try:
        # Fetch Target Ticker
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url)
        data = r.json()
        
        # Check for API Limits (Common in Free Tier)
        if "Note" in data:
            return "LIMIT", None, None
        if "Error Message" in data:
            return "INVALID", None, None
            
        # Fetch SPY Benchmark
        url_spy = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=SPY&apikey={AV_KEY}'
        r_spy = requests.get(url_spy)
        data_spy = r_spy.json()
        
        if "Note" in data_spy:
            return "LIMIT", None, None

        # Process Main Ticker
        df = pd.DataFrame.from_dict(data['Time Series (Daily)'], orient='index').astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().rename(columns={'1. open':'Open','2. high':'High','3. low':'Low','4. close':'Close','5. volume':'Volume'})
        
        # Process SPY
        spy = pd.DataFrame.from_dict(data_spy['Time Series (Daily)'], orient='index').astype(float)
        spy.index = pd.to_datetime(spy.index)
        spy = spy.sort_index()['4. close']

        # Sync dates
        common_dates = df.index.intersection(spy.index)
        df = df.loc[common_dates]
        spy = spy.loc[common_dates]

        return "OK", df, spy
    except Exception as e:
        return str(e), None, None

# Trigger Data Fetch
status, df, spy_price = get_full_market_data(ticker)

# --- 3. DASHBOARD LOGIC ---
if status == "OK":
    # MATH SECTION
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['Net_Flow'] = np.where(df['Close'] > df['Close'].shift(1), df['TP'] * df['Volume'], -df['TP'] * df['Volume'])
    df['Flow_EMA'] = df['Net_Flow'].ewm(span=10).mean()
    df['RS_Line'] = (df['Close'] / df['Close'].iloc[0]) / (spy_price / spy_price.iloc[0])
    df['Avg_Vol'] = df['Volume'].rolling(20).mean()
    df['RVOL'] = df['Volume'] / df['Avg_Vol']
    df['Vol'] = df['Close'].pct_change().rolling(20).std() * (252**0.5) * 100
    df['Threshold'] = df['Vol'].rolling(60).mean() + (1.5 * df['Vol'].rolling(60).std())

    # --- UI RENDERING ---
    st.title(f"🚀 {ticker} Conviction Terminal")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Price", f"${df['Close'].iloc[-1]:.2f}")
    c2.metric("RVOL (Whales)", f"{df['RVOL'].iloc[-1]:.1f}x")
    c3.metric("Fear Index", f"{df['Vol'].iloc[-1]:.1f}%")
    flow_val = df['Net_Flow'].iloc[-1]
    flow_disp = f"${flow_val/1e9:.1f}B" if abs(flow_val) >= 1e9 else f"${flow_val/1e6:.1f}M"
    c4.metric("Inst. Flow", flow_disp)

    # Chart
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price", line=dict(color="#003366", width=3)), secondary_y=False)
    recent = df.tail(60)
    fig.add_trace(go.Bar(x=recent.index, y=recent['Net_Flow'], name="Net Flow", 
                         marker_color=np.where(recent['Net_Flow']>0, '#26a69a', '#ef5350'), opacity=0.4), secondary_y=True)
    fig.update_layout(template="plotly_white", height=500, paper_bgcolor="white", font=dict(color="black"))
    fig.update_yaxes(tickformat="~s", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    # Summary
    st.subheader("🎯 Final Conviction Score")
    with st.container(border=True):
        col_a, col_b, col_c = st.columns(3)
        if df['RVOL'].iloc[-1] > 1.5:
            col_a.success(f"🐳 **WHALE ACTIVITY DETECTED**")
        else:
            col_a.info(f"🐟 **RETAIL VOLUME**")
        
        if df['RS_Line'].iloc[-1] > 1:
            col_b.success("🏆 **OUTPERFORMING MARKET**")
        else:
            col_b.error("📉 **LAGGING MARKET**")

        if df['Net_Flow'].iloc[-1] > 0 and df['RVOL'].iloc[-1] > 1.2:
            col_c.markdown("### 🏹 SIGNAL: BUY")
        else:
            col_c.markdown("### ⚖️ SIGNAL: NEUTRAL")

elif status == "LIMIT":
    st.error("🚨 **API Limit Reached!** Alpha Vantage free tier allows 25 requests/day. Please wait 24 hours or use a different API key.")
elif status == "INVALID":
    st.warning("❌ **Ticker Not Found.** Please check the symbol and try again.")
else:
    st.error(f"System Error: {status}")
