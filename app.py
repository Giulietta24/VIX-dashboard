import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time  # New import for the delay

# --- 1. SETUP & SECRETS ---
try:
    AV_KEY = st.secrets["AV_KEY"]
except:
    st.error("Missing 'AV_KEY' in Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="High-Certainty Terminal", layout="wide")
ticker = st.sidebar.text_input("Enter Ticker", "SPY").upper()

# --- 2. THE DATA ENGINE (With Anti-Crash Delay) ---
@st.cache_data(ttl=3600)
def get_full_market_data(symbol):
    try:
        # Request 1: Target Ticker
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url)
        data = r.json()
        
        if "Note" in data: return "LIMIT", None, None
        if "Error Message" in data: return "INVALID", None, None
        if 'Time Series (Daily)' not in data: return "API_REJECTION", None, None

        # DELAY: Give the API a break (Free tier requirement)
        time.sleep(2) 

        # Request 2: SPY Benchmark
        url_spy = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=SPY&apikey={AV_KEY}'
        r_spy = requests.get(url_spy)
        data_spy = r_spy.json()
        
        if 'Time Series (Daily)' not in data_spy: return "LIMIT", None, None

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

# --- 3. UI RENDERING ---
if status == "OK":
    # MATH
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['Net_Flow'] = np.where(df['Close'] > df['Close'].shift(1), df['TP'] * df['Volume'], -df['TP'] * df['Volume'])
    df['Flow_EMA'] = df['Net_Flow'].ewm(span=10).mean()
    df['RS_Line'] = (df['Close'] / df['Close'].iloc[0]) / (spy_price / spy_price.iloc[0])
    df['RVOL'] = df['Volume'] / df['Volume'].rolling(20).mean()
    df['Vol'] = df['Close'].pct_change().rolling(20).std() * (252**0.5) * 100
    df['Threshold'] = df['Vol'].rolling(60).mean() + (1.5 * df['Vol'].rolling(60).std())

    st.title(f"🚀 {ticker} Conviction Terminal")
    
    # Visuals
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price", line=dict(color="#003366", width=3)), secondary_y=False)
    
    recent = df.tail(60)
    fig.add_trace(go.Bar(x=recent.index, y=recent['Net_Flow'], name="Net Flow", 
                         marker_color=np.where(recent['Net_Flow']>0, '#26a69a', '#ef5350'), opacity=0.4), secondary_y=True)
    
    fig.update_layout(template="plotly_white", height=500, paper_bgcolor="white", font=dict(color="black"), hovermode="x unified")
    fig.update_yaxes(tickformat="~s", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    # Verdict
    st.subheader("🎯 Conviction Summary")
    with st.container(border=True):
        if df['Net_Flow'].iloc[-1] > 0 and df['RVOL'].iloc[-1] > 1.2:
            st.success("🏹 **HIGH CONVICTION BUY:** Institutional flow + High Volume + Market Strength.")
        else:
            st.info("⚖️ **NEUTRAL:** Waiting for whale confirmation.")

elif status == "LIMIT":
    st.error("🚨 **Daily Limit Reached (25/day).** Try a new API key or wait 24 hours.")
elif status == "API_REJECTION":
    st.warning("⚠️ **API Busy.** Refresh the page in 5 seconds to try again.")
else:
    st.error(f"Error: {status}")
