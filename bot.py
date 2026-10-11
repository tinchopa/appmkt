import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# Claves inyectadas por GitHub Actions
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

acciones = [
    "GOOG", "AMD", "ALAB", "C", "LLY", "GE", "URA", "IBM", "JMIA", 
    "LRCX", "MCD", "MELI", "META", "MU", "MSFT", "NU", "NVDA", "OKLO", 
    "PLTR", "PAAS", "PEP", "QCOM", "RGTI", "HOOD", "TEM", 
    "TSLA", "PATH", "UNH", "SPY"
]

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
    except:
        pass

def radar_acciones():
    for ticker in acciones:
        try:
            # Ampliamos a '1y' (1 año) para tener suficientes días para calcular la EMA 200
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            # --- 1. CÁLCULO DE INDICADORES ---
            df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()
            df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
            
            # RSI
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df["RSI"] = 100 - (100 / (1 + rs))

            # MACD y Bollinger
            ema_12 = df["Close"].ewm(span=12, adjust=False).mean()
            ema_26 = df["Close"].ewm(span=26, adjust=False).mean()
            macd = ema_12 - ema_26
            macd_sig = macd.ewm(span=9, adjust=False).mean()
            
            bb_mid = df["Close"].rolling(window=20).mean()
            std = df["Close"].rolling(window=20).std()
            bb_width = (bb_mid + (2 * std) - (bb_mid - (2 * std))) / bb_mid
            
            # Variables de la vela actual
            ultimo = df.iloc[-1]
            precio = float(ultimo["Close"])
            atr = float(ultimo["ATR"])
            rsi = float(ultimo["RSI"])
            ema_200 = float(ultimo["EMA_200"])
            
            # --- 2. RADARES DE TRADING FILTRADOS ---
            
            # RADAR 1: FIBONACCI (50%)
            max_30 = df["High"].tail(30).max()
            min_30 = df["Low"].tail(30).min()
            impulso = max_30 - min_30
            if impulso > 0 and max_30 > min_30:
                fib_50 = max_30 - (impulso * 0.50)
                if abs(precio - fib_50) / fib_50 < 0.01:
                    sl = precio - (1.5 * atr)
                    tp = precio + (2.5 * atr)
                    enviar_telegram(f"📐 *FIBONACCI: {ticker}*\nRebote en 50%.\nPrecio: ${precio:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f}")

            # RADAR 2: BOLLINGER + MACD
            if float(bb_width.iloc[-1]) < 0.05 and float(macd.iloc[-1]) > float(macd_sig.iloc[-1]) and float(macd.iloc[-2]) <= float(macd_sig.iloc[-2]):
                sl = precio - (1.5 * atr)
                tp = precio + (3.0 * atr)
                enviar_telegram(f"💥 *BOLLINGER/MACD: {ticker}*\nExplosión alcista inminente.\nPrecio: ${precio:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f}")

            # RADAR 3: CAZA-REBOTES (RSI Sobreventa Extrema)
            # Riesgo ajustado para capturar el rebote corto
            if rsi < 30:
                sl = precio - (2.5 * atr)
                tp = precio + (2.0 * atr)
                enviar_telegram(f"🚨 *SOBREVENTA EXTREMA: {ticker}*\nRSI por el piso ({rsi:.1f}). Posible rebote rápido.\nPrecio: ${precio:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f}")

            # RADAR 4: BREAKOUT (Quiebre con Filtro Macro EMA 200)
            # Riesgo 1:2 (Arriesga 1.5 ATR, busca 3.0 ATR)
            max_20_previo = df["High"].iloc[-21:-1].max()
            if precio > max_20_previo and df["Close"].iloc[-2] <= max_20_previo and precio > ema_200:
                sl = precio - (1.5 * atr)
                tp = precio + (3.0 * atr)
                enviar_telegram(f"🚀 *BREAKOUT ALCISTA: {ticker}*\nRompió techo a favor de tendencia macro.\nPrecio: ${precio:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f}")

        except Exception as e:
            continue

if __name__ == "__main__":
    radar_acciones()
