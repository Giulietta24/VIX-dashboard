@st.cache_data(ttl=3600)
def get_full_market_data(symbol):
    try:
        # Fetch Target Ticker
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url)
        data = r.json()
        
        # Check for API Limit 'Note'
        if "Note" in data:
            return "LIMIT_REACHED", None, None
        
        # Check for Invalid Ticker
        if "Error Message" in data:
            return "INVALID_TICKER", None, None

        # Verify the key exists before trying to use it (Fixes image_d43db3.png)
        if 'Time Series (Daily)' not in data:
            return "MISSING_DATA", None, None

        # Fetch SPY Benchmark
        url_spy = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=SPY&apikey={AV_KEY}'
        r_spy = requests.get(url_spy)
        data_spy = r_spy.json()

        if 'Time Series (Daily)' not in data_spy:
            return "LIMIT_REACHED", None, None

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
        return f"ERROR: {str(e)}", None, None

# Trigger Data Fetch
status, df, spy_price = get_full_market_data(ticker)

# --- 3. ERROR HANDLING UI ---
if status == "LIMIT_REACHED":
    st.error("🚨 **Daily API Limit Reached (25/day)**")
    st.info("Alpha Vantage has cut off the data for today. To keep testing, you can sign up for a new free key with a different email and update your 'Secrets' in Streamlit.")
    st.stop() # Stops the rest of the app from running and crashing
elif status == "INVALID_TICKER":
    st.warning(f"❌ Ticker '{ticker}' not found. Please check the symbol.")
    st.stop()
elif status != "OK":
    st.error(f"Something went wrong: {status}")
    st.stop()

# --- 4. REST OF YOUR DASHBOARD LOGIC HERE ---
# (Only runs if status is "OK")
