import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Scanner CEDEARs", layout="centered")
st.title("📱 Scanner Técnico: US / CEDEARs")

Ratios = {
    "GOOG": 58, "AMD": 10, "ALAB": 44, "C": 3, "LLY": 56, "GE": 8, 
    "URA": 5, "IBM": 15, "JMIA": 2, "LRCX": 56, "MCD": 24, "MELI": 120, 
    "META": 24, "MU": 12, "MSFT": 30, "NU": 1, "NVDA": 24, "OKLO": 1, 
    "PLTR": 1, "PAWN": 1, "PAAS": 1, "PEP": 6, "QCOM": 11, "RGTI": 2, 
    "HOOD": 2, "TEM": 1, "TSLA": 15, "PATH": 2, "UNH": 33, "SPY": 60
}
ticker = st.selectbox("Selecciona el Activo", list(Ratios.keys()))

@st.cache_data(ttl=3600)
def obtener_datos(ticker_us):
    us_data = yf.download(ticker_us, period="6mo", interval="1d", progress=False)
    ba_data = yf.download(f"{ticker_us}.BA", period="5d", interval="1d", progress=False)
    return us_data, ba_data

us_data, ba_data = obtener_datos(ticker)

if not us_data.empty and not ba_data.empty:
    if isinstance(us_data.columns, pd.MultiIndex): us_data.columns = us_data.columns.get_level_values(0)
    if isinstance(ba_data.columns, pd.MultiIndex): ba_data.columns = ba_data.columns.get_level_values(0)

    df = us_data.copy()
    df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
    
    ultimo = df.iloc[-1]
    precio_usd = float(ultimo["Close"])
    
    precio_ars = float(ba_data["Close"].iloc[-1])
    ccl_implicito = (precio_ars * Ratios[ticker]) / precio_usd

    st.subheader(f"💵 {ticker} - Datos de Mercado")
    c1, c2 = st.columns(2)
    c1.metric("Precio USD", f"${precio_usd:.2f}")
    c2.metric("Precio ARS", f"${precio_ars:,.2f}")
    st.metric("CCL Implícito", f"${ccl_implicito:,.2f}")
    
    st.line_chart(df[["Close", "EMA_20", "EMA_50"]].tail(90))
