import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="ETF Flow Terminal", layout="wide")
ticker = st.sidebar.text_input("Enter ETF", "PAVE").upper()

@st.cache_data(ttl=3600)
def get_data(symbol):
    t = yf.Ticker(symbol)
    hist = t.history(period="1y")
    return hist, t.info

hist, info = get_data(ticker)

if not hist.empty:
    # --- CALCULATE "SYNTHETIC" INSTITUTIONAL FLOW ---
    hist['TP'] = (hist['High'] + hist['Low'] + hist['Close']) / 3
    hist['Flow'] = hist['TP'] * hist['Volume']
    # If price goes up, money is "Entering"; if down, money is "Exiting"
    hist['Net_Flow'] = np.where(hist['Close'] > hist['Close'].shift(1), hist['Flow'], -hist['Flow'])
    # Smooth it out to look like ETF.com
    hist['Flow_Trend'] = hist['Net_Flow'].ewm(span=5).mean()

    # --- UI ---
    st.title(f"📊 {ticker} Intelligence")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Price
    fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Price", line=dict(color="#ffffff")), secondary_y=False)
    
    # Capital Flow Bars
    recent = hist.tail(50)
    fig.add_trace(go.Bar(x=recent.index, y=recent['Net_Flow'], name="Daily Flow", 
                         marker_color=np.where(recent['Net_Flow']>0, '#00ff00', '#ff0000'), opacity=0.3), secondary_y=True)
    
    # The "FactSet Style" Trend Line
    fig.add_trace(go.Scatter(x=recent.index, y=recent['Flow_Trend'], name="Flow Trend", 
                             line=dict(color="#00fbff", width=2)), secondary_y=True)

    fig.update_layout(template="plotly_dark", height=600)
    st.plotly_chart(fig, use_container_width=True)
    
    # FEAR GAUGE (VIX)
    st.subheader("🔥 Market Fear Gauge")
    hist['VIX'] = hist['Close'].pct_change().rolling(20).std() * (252**0.5) * 100
    st.line_chart(hist['VIX'])
