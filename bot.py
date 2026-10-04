import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# GitHub inyectará estas claves secretamente
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

acciones = [
    "GOOG", "AMD", "ALAB", "C", "LLY", "GE", "URA", "IBM", "JMIA", 
    "LRCX", "MCD", "MELI", "META", "MU", "MSFT", "NU", "NVDA", "OKLO", 
    "PLTR", "PAWN", "PAAS", "PEP", "QCOM", "RGTI", "HOOD", "TEM", 
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
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            # EMA y ATR
            df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
            df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
            df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()
            
            ultimo = df.iloc[-1]
            precio = float(ultimo["Close"])
            atr = float(ultimo["ATR"])
            
            # RADAR 1: FIBONACCI
            max_30, min_30 = df["High"].tail(30).max(), df["Low"].tail(30).min()
            impulso = max_30 - min_30
            if impulso > 0 and max_30 > min_30:
                fib_50 = max_30 - (impulso * 0.50)
                if abs(precio - fib_50) / fib_50 < 0.01:
                    sl = precio - (1.5 * atr)
                    tp = precio + (2.5 * atr)
                    enviar_telegram(f"📐 *RADAR FIBONACCI: {ticker}*\nRebote en 50%.\nPrecio: \({precio:.2f} | SL:\){sl:.2f} | TP: ${tp:.2f}")

        except Exception as e:
            continue

if __name__ == "__main__":
    radar_acciones()
