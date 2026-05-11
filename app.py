import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ... (Previous code for caching and price data) ...

@st.cache_data(ttl=3600)
def get_implied_vol(symbol):
    try:
        t = yf.Ticker(symbol)
        # 1. Get the closest monthly expiry (approx 30 days out)
        expiries = t.options
        if not expiries: return None
        
        # 2. Pick an expiry that is at least 20 days away
        target_expiry = expiries[0] 
        for date in expiries:
            days_out = (pd.to_datetime(date) - pd.Timestamp.today()).days
            if days_out > 20:
                target_expiry = date
                break
        
        # 3. Get the option chain
        opt = t.option_chain(target_expiry)
        # Average the IV of the ATM Call and Put
        calls_iv = opt.calls['impliedVolatility'].iloc[len(opt.calls)//2]
        puts_iv = opt.puts['impliedVolatility'].iloc[len(opt.puts)//2]
        
        return (calls_iv + puts_iv) / 2 * 100 # Convert to percentage
    except:
        return None

# Add to your Dashboard UI
ticker_iv = get_implied_vol(ticker)

if ticker_iv:
    st.sidebar.metric("Implied Volatility (IV)", f"{ticker_iv:.1f}%")
    
    # Logic: Compare IV to the VIX Proxy (Historical)
    if ticker_iv > current_vix + 5:
        st.warning(f"⚠️ **IV SKEW:** Traders are expecting MORE volatility ({ticker_iv:.1f}%) than we've seen recently ({current_vix:.1f}%).")
