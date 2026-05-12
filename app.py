@st.cache_data(ttl=3600)
def get_alpha_data(symbol):
    try:
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(url)
        data = r.json()
        
        # 1. Check for the "Note" (Limit Reached)
        if "Note" in data:
            st.error("🚨 **API Limit Reached:** Alpha Vantage allows 25 requests per day. You've hit the limit.")
            return "LIMIT", None
        
        # 2. Check for "Error Message" (Invalid Key or Ticker)
        if "Error Message" in data:
            st.error(f"❌ **API Error:** {data['Error Message']}")
            return "ERROR", None
            
        # 3. If data is there, proceed
        if 'Time Series (Daily)' in data:
            df = pd.DataFrame.from_dict(data['Time Series (Daily)'], orient='index')
            df = df.astype(float)
            df.index = pd.to_datetime(df.index)
            df = df.sort_index().rename(columns={
                '1. open': 'Open', '2. high': 'High', 
                '3. low': 'Low', '4. close': 'Close', '5. volume': 'Volume'
            })
            return "OK", df
        
        # 4. Catch-all for weird responses
        st.warning(f"Unexpected response: {list(data.keys())}")
        return "UNKNOWN", None

    except Exception as e:
        st.error(f"System Error: {e}")
        return "SYSTEM_ERROR", None
