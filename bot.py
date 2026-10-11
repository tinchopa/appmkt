import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# Claves inyectadas por GitHub Actions
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Tu lista limpia de 29 acciones
acciones = [
    "GOOG", "AMD", "ALAB", "C", "LLY", "GE", "URA", "IBM", "JMIA", 
    "LRCX", "MCD", "MELI", "META", "MU", "MSFT", "NU", "NVDA", "OKLO", 
    "PLTR", "PAAS", "PEP", "QCOM", "RGTI", "HOOD", "TEM", 
    "TSLA", "PATH", "UNH", "SPY"
]

# Diccionario de ratios de CEDEARs (Ajustar si hay nuevos splits en el mercado)
ratios_cedear = {
    "GOOG": 58, "AMD": 0.5, "C": 3, "LLY": 60, "GE": 8, "IBM": 5, 
    "MCD": 24, "MELI": 60, "META": 24, "MU": 12, "MSFT": 30, "NU": 1, 
    "NVDA": 240, "PLTR": 1, "PAAS": 1, "PEP": 6, "QCOM": 11, "TSLA": 15, 
    "UNH": 33, "SPY": 20
}

# Capital fijo por operación en ARS (Modificá este valor según el tamaño de tu cuenta)
CAPITAL_POR_TRADE = 1000000 

def obtener_ccl():
    try:
        respuesta = requests.get("https://dolarapi.com/v1/dolares/contadoconliqui").json()
        return float(respuesta["venta"])
    except:
        return 1200.0 # Valor de contingencia por si la API falla

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
    except:
        pass

def radar_acciones():
    ccl = obtener_ccl() # Consultamos el dólar una sola vez al iniciar el escaneo
    
    for ticker in acciones:
        try:
            # 1 año de historia para poder calcular la EMA 200
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            # --- CÁLCULO DE INDICADORES ---
            df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()
            df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
            
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df["RSI"] = 100 - (100 / (1 + rs))

            ema_12 = df["Close"].ewm(span=12, adjust=False).mean()
            ema_26 = df["Close"].ewm(span=26, adjust=False).mean()
            macd = ema_12 - ema_26
            macd_sig = macd.ewm(span=9, adjust=False).mean()
            
            bb_mid = df["Close"].rolling(window=20).mean()
            std = df["Close"].rolling(window=20).std()
            bb_width = (bb_mid + (2 * std) - (bb_mid - (2 * std))) / bb_mid
            
            # Variables de la vela actual
            precio = float(df["Close"].iloc[-1])
            atr = float(df["ATR"].iloc[-1])
            rsi = float(df["RSI"].iloc[-1])
            ema_200 = float(df["EMA_200"].iloc[-1])
            ratio = ratios_cedear.get(ticker, 1) # Si no está en el dict, usa 1
            precio_cedear_ars = (precio / ratio) * ccl
            
            # Evitar división por cero si el precio es ínfimo
            if precio_cedear_ars <= 0: continue
            nominales = int(CAPITAL_POR_TRADE / precio_cedear_ars)
            
            # --- RADARES DE TRADING FILTRADOS Y OPTIMIZADOS ---
            
            # RADAR 1: FIBONACCI (50%)
            max_30 = df["High"].tail(30).max()
            min_30 = df["Low"].tail(30).min()
            impulso = max_30 - min_30
            if impulso > 0 and max_30 > min_30:
                fib_50 = max_30 - (impulso * 0.50)
                if abs(precio - fib_50) / fib_50 < 0.01:
                    sl, tp = precio - (1.5 * atr), precio + (2.5 * atr)
                    mensaje = (
                        f"📐 *FIBONACCI: {ticker}*\n"
                        f"Rebote en 50% del impulso.\n"
                        f"📊 *Límite:* ${precio_cedear_ars:,.2f} ARS | 🛒 *Comprar:* {nominales} un.\n"
                        f"🎯 TP: ${tp:.2f} USD | 🛑 SL: ${sl:.2f} USD\n"
                        f"*(CCL: ${ccl:.2f} | Ratio: {ratio})*"
                    )
                    enviar_telegram(mensaje)

            # RADAR 2: BOLLINGER + MACD
            if float(bb_width.iloc[-1]) < 0.05 and float(macd.iloc[-1]) > float(macd_sig.iloc[-1]) and float(macd.iloc[-2]) <= float(macd_sig.iloc[-2]):
                sl, tp = precio - (1.5 * atr), precio + (3.0 * atr)
                mensaje = (
                    f"💥 *BOLLINGER/MACD: {ticker}*\n"
                    f"Explosión alcista por compresión.\n"
                    f"📊 *Límite:* ${precio_cedear_ars:,.2f} ARS | 🛒 *Comprar:* {nominales} un.\n"
                    f"🎯 TP: ${tp:.2f} USD | 🛑 SL: ${sl:.2f} USD\n"
                    f"*(CCL: ${ccl:.2f} | Ratio: {ratio})*"
                )
                enviar_telegram(mensaje)

            # RADAR 3: CAZA-REBOTES (RSI Sobreventa Extrema)
            if rsi < 30:
                sl, tp = precio - (2.5 * atr), precio + (2.0 * atr)
                mensaje = (
                    f"🚨 *SOBREVENTA EXTREMA: {ticker}*\n"
                    f"RSI en {rsi:.1f}. Posible rebote corto.\n"
                    f"📊 *Límite:* ${precio_cedear_ars:,.2f} ARS | 🛒 *Comprar:* {nominales} un.\n"
                    f"🎯 TP: ${tp:.2f} USD | 🛑 SL: ${sl:.2f} USD\n"
                    f"*(CCL: ${ccl:.2f} | Ratio: {ratio})*"
                )
                enviar_telegram(mensaje)

            # RADAR 4: BREAKOUT (Quiebre con Filtro Macro EMA 200)
            max_20_previo = df["High"].iloc[-21:-1].max()
            if precio > max_20_previo and df["Close"].iloc[-2] <= max_20_previo and precio > ema_200:
                sl, tp = precio - (1.5 * atr), precio + (3.0 * atr)
                mensaje = (
                    f"🚀 *BREAKOUT ALCISTA: {ticker}*\n"
                    f"Quiebre a favor de tendencia macro.\n"
                    f"📊 *Límite:* ${precio_cedear_ars:,.2f} ARS | 🛒 *Comprar:* {nominales} un.\n"
                    f"🎯 TP: ${tp:.2f} USD | 🛑 SL: ${sl:.2f} USD\n"
                    f"*(CCL: ${ccl:.2f} | Ratio: {ratio})*"
                )
                enviar_telegram(mensaje)

        except Exception as e:
            continue

if __name__ == "__main__":
    radar_acciones()
