# --- ADD THIS INSIDE YOUR MATH SECTION ---
# 1. Relative Volume (RVOL)
df['Avg_Vol'] = df['Volume'].rolling(20).mean()
df['RVOL'] = df['Volume'] / df['Avg_Vol']

# 2. Relative Strength (RS) - Needs SPY data
@st.cache_data(ttl=3600)
def get_spy_bench():
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=SPY&apikey={AV_KEY}'
    r = requests.get(url).json()
    spy = pd.DataFrame.from_dict(r['Time Series (Daily)'], orient='index').astype(float)
    return spy['4. close'].sort_index()

spy_price = get_spy_bench()
# Align dates and calculate RS
df['RS'] = (df['Close'] / df['Close'].iloc[0]) / (spy_price / spy_price.iloc[0])

# --- ADD THIS TO YOUR SUMMARY SECTION ---
with st.container(border=True):
    st.subheader("🎯 Conviction Score")
    col_x, col_y, col_z = st.columns(3)
    
    # RVOL Check
    curr_rvol = df['RVOL'].iloc[-1]
    if curr_rvol > 2:
        col_x.error(f"🔥 **ULTRA VOLUME:** {curr_rvol:.1f}x normal. Heavy Whale activity!")
    elif curr_rvol > 1.2:
        col_x.warning(f"✅ **High Volume:** {curr_rvol:.1f}x normal.")
    else:
        col_x.info(f"⚪ **Low Volume:** {curr_rvol:.1f}x. Retail noise.")

    # RS Check
    curr_rs = df['RS'].iloc[-1]
    if curr_rs > 1.05:
        col_y.success(f"🏆 **Outperforming Market:** Beating SPY by {((curr_rs-1)*100):.1f}%")
    else:
        col_y.error("📉 **Underperforming:** Weakness vs SPY.")
        
    # Final Verdict
    if curr_rvol > 1.2 and curr_rs > 1 and curr_flow > 0:
        col_z.markdown("### 🏹 BUY SIGNAL: HIGH")
    elif curr_rvol > 1.2 and curr_flow < 0:
        col_z.markdown("### 🛡️ SELL SIGNAL: HIGH")
    else:
        col_z.markdown("### ⚖️ NEUTRAL")
