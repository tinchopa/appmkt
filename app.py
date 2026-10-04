import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Scanner CEDEARs", layout="centered")
st.title("📱 Scanner Técnico: US / CEDEARs")

# Lista ampliada de 30 activos
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
    
    # Indicadores
    df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
    
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df["RSI"] = 100 - (100 / (1 + (gain / loss)))

    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    df["ATR"] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()

    ultimo = df.iloc[-1]
    precio_usd = float(ultimo["Close"])
    rsi_actual = float(ultimo["RSI"])
    atr = float(ultimo["ATR"])
    
    precio_ars = float(ba_data["Close"].iloc[-1])
    ccl_implicito = (precio_ars * Ratios[ticker]) / precio_usd

    # Cálculos Operativos (Riesgo/Beneficio para Swing Corto)
    sl_usd = precio_usd - (1.5 * atr)
    tp_usd = precio_usd + (2.5 * atr) 

    precio_cedear_ars = (precio_usd / Ratios[ticker]) * ccl_implicito
    sl_cedear_ars = (sl_usd / Ratios[ticker]) * ccl_implicito
    tp_cedear_ars = (tp_usd / Ratios[ticker]) * ccl_implicito

    # --- INTERFAZ VISUAL ---
    st.subheader(f"💵 {ticker} - Datos de Mercado")
    c1, c2 = st.columns(2)
    c1.metric("Precio USD", f"${precio_usd:.2f}")
    c2.metric("Precio ARS", f"${precio_ars:,.2f}")
    
    c3, c4 = st.columns(2)
    c3.metric("RSI (14)", f"{rsi_actual:.1f}")
    c4.metric("CCL Implícito", f"${ccl_implicito:,.2f}")

    st.divider()
    
    st.subheader("🎯 Setup Técnico Sugerido")
    st.caption("Swing corto basado en volatilidad (ATR)")
    
    st.markdown("**🟢 Punto de Entrada:**")
    st.code(f"USD: \({precio_usd:.2f}  |  ARS:\){precio_cedear_ars:,.2f}")
    
    st.markdown("**🔴 Stop Loss (SL):**")
    st.code(f"USD: \({sl_usd:.2f}     |  ARS:\){sl_cedear_ars:,.2f}")
    
    st.markdown("**🔵 Take Profit (TP):**")
    st.code(f"USD: \({tp_usd:.2f}     |  ARS:\){tp_cedear_ars:,.2f}")

    st.divider()
    
    st.subheader("📊 Gráfico de Tendencia (90 días)")
    st.line_chart(df[["Close", "EMA_20", "EMA_50"]].tail(90))
    
    # Leyenda Explicativa
    st.info("""
    **Cómo leer este gráfico en 3 segundos:**
    
    * **Close (Precio):** El valor real de la acción.
    * **EMA 20 (Línea rápida):** Tu piso dinámico. En una tendencia alcista sana, el precio rebota acá. Es tu zona ideal de compra (*pullback*).
    * **EMA 50 (Línea general):** Tu filtro de seguridad. Si el precio y la EMA 20 rompen hacia abajo esta línea, indica peligro o cambio de tendencia.
    
    *Consejo:* Si las líneas están muy juntas, horizontales y cruzándose todo el tiempo, el activo está lateralizando (sin tendencia). Mejor buscar otro.
    """)
else:
    st.error("No se pudieron obtener los datos. Intentá en un momento.")
