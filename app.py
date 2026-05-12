import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. ACCESS SECRETS ---
try:
    AV_KEY = st.secrets["AV_KEY"]
except:
    st.error("Missing 'AV_KEY' in Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="ETF Sentiment Terminal", layout="wide")

ticker = st.sidebar.text_input("Enter Ticker", "SPY").upper()

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=3600)
def get_alpha_data(symbol):
    try:
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url)
        data = r.json()
        if "Note" in data: return "LIMIT", None
        if "Error Message" in data: return "INVALID", None
        
        df = pd.DataFrame.from_dict(data['Time Series (Daily)'], orient='index')
        df = df.astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().rename(columns={
            '1. open': 'Open', '2. high': 'High', 
            '3. low': 'Low', '4. close': 'Close', '5. volume': 'Volume'
        })
        return "OK", df
    except Exception as e:
        return str(e), None

status, df = get_alpha_data(ticker)

# --- 3. DASHBOARD ---
if status == "OK":
    # --- MATH ---
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['Net_Flow'] = np.where(df['Close'] > df['Close'].shift(1), 
                              df['TP'] * df['Volume'], -df['TP'] * df['Volume'])
    df['Flow_EMA'] = df['Net_Flow'].ewm(span=10).mean()
    df['Vol'] = df['Close'].pct_change().rolling(20).std() * (252**0.5) * 100
    df['Threshold'] = df['Vol'].rolling(60).mean() + (1.5 * df['Vol'].rolling(60).std())

    st.title(f"📈 {ticker} Intelligence Terminal")
    
    # Metrics
    flow_val = df['Net_Flow'].iloc[-1]
    flow_disp = f"${flow_val/1e9:.2f}B" if abs(flow_val) >= 1e9 else f"${flow_val/1e6:.1f}M"
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"${df['Close'].iloc[-1]:.2f}")
    c2.metric("Fear Index (VIX)", f"{df['Vol'].iloc[-1]:.1f}%")
    c3.metric("Daily Money Flow", flow_disp)

    # --- CHART 1: SENTIMENT & FLOW (LIGHT MODE) ---
    st.subheader("💳 Institutional Sentiment & Price Action")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Price Line (Dark Blue for visibility on white)
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price", 
                             line=dict(color="#003366", width=3)), secondary_y=False)
    
    # Net Flow Bars
    recent = df.tail(60)
    fig.add_trace(go.Bar(x=recent.index, y=recent['Net_Flow'], name="Net Flow", 
                         marker_color=np.where(recent['Net_Flow']>0, '#26a69a', '#ef5350'), 
                         opacity=0.5), secondary_y=True)
    
    # Flow Trend Line (Bright Blue)
    fig.add_trace(go.Scatter(x=recent.index, y=recent['Flow_EMA'], name="Flow Trend", 
                             line=dict(color="#007bff", width=2)), secondary_y=True)
    
    # Layout Adjustments for White Background
    fig.update_layout(
        template="plotly_white", # Switch to white template
        height=500, 
        hovermode="x unified",
        paper_bgcolor="white", 
        plot_bgcolor="white",
        font=dict(color="black"), # All text to black
        legend=dict(orientation="h", y=1.1, font=dict(color="black"))
    )

    fig.update_yaxes(title_text="Price ($)", secondary_y=False, showgrid=True, gridcolor='lightgray', title_font=dict(color="black"), tickfont=dict(color="black"))
    fig.update_yaxes(title_text="Capital Flow ($)", secondary_y=True, tickformat="~s", showgrid=False, title_font=dict(color="black"), tickfont=dict(color="black"))
    fig.update_xaxes(showgrid=True, gridcolor='lightgray', tickfont=dict(color="black"))
    
    st.plotly_chart(fig, use_container_width=True)

    # --- CHART 2: FEAR (LIGHT MODE) ---
    st.subheader("🔥 Dynamic Panic Threshold")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df.index, y=df['Vol'], name="Volatility", fill='tozeroy', line=dict(color="orange")))
    fig2.add_trace(go.Scatter(x=df.index, y=df['Threshold'], name="Panic Line", line=dict(color="red", dash="dash")))
    
    fig2.update_layout(
        template="plotly_white", 
        height=350, 
        paper_bgcolor="white", 
        plot_bgcolor="white",
        font=dict(color="black"),
        legend=dict(orientation="h", y=1.1, font=dict(color="black"))
    )
    fig2.update_yaxes(title_text="Volatility %", gridcolor='lightgray', tickfont=dict(color="black"))
    fig2.update_xaxes(gridcolor='lightgray', tickfont=dict(color="black"))
    
    st.plotly_chart(fig2, use_container_width=True)

elif status == "LIMIT":
    st.warning("⚠️ API Limit Reached.")
else:
    st.error(f"Error: {status}")
