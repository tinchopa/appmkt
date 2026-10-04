import yfinance as yf
import pandas as pd
import numpy as np
import requests

# --- CONFIGURACIÓN DE TELEGRAM ---
import os
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


# --- LISTAS DE ACTIVOS ---
acciones = ["AAPL", "MSFT", "SPY", "QQQ", "TSLA", "NVDA", "KO"]
bonos = ["AL35.BA", "TX26.BA", "DICP.BA", "AO28.BA"]

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Error Telegram: {e}")

def calcular_indicadores_base(df):
    df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
    
    # ATR
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    df["ATR"] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    # MACD
    ema_12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema_12 - ema_26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    
    # Bollinger Bands
    df["BB_Mid"] = df["Close"].rolling(window=20).mean()
    std = df["Close"].rolling(window=20).std()
    df["BB_Up"] = df["BB_Mid"] + (2 * std)
    df["BB_Low"] = df["BB_Mid"] - (2 * std)
    # Ancho de las bandas (para medir compresión)
    df["BB_Width"] = (df["BB_Up"] - df["BB_Low"]) / df["BB_Mid"]
    
    return df

def radar_acciones():
    print("Radar 1 y 2: Escaneando Acciones EE.UU...")
    for ticker in acciones:
        try:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            df = calcular_indicadores_base(df)
            ultimo = df.iloc[-1]
            precio = float(ultimo["Close"])
            atr = float(ultimo["ATR"])
            
            # --- RADAR 1: FIBONACCI (Retrocesos) ---
            # Calculamos el max y min de los últimos 30 días para trazar Fibonacci
            max_30 = df["High"].tail(30).max()
            min_30 = df["Low"].tail(30).min()
            impulso = max_30 - min_30
            
            # Solo analizamos si hay un impulso alcista claro previo (precio actual > min_30)
            if impulso > 0 and max_30 > min_30:
                fib_50 = max_30 - (impulso * 0.50)
                fib_618 = max_30 - (impulso * 0.618)
                
                # Gatillo: Precio tocando el 50% o 61.8% (margen del 1%)
                toca_50 = abs(precio - fib_50) / fib_50 < 0.01
                toca_618 = abs(precio - fib_618) / fib_618 < 0.01
                
                if toca_50 or toca_618:
                    nivel = "50%" if toca_50 else "61.8%"
                    sl = precio - (1.5 * atr)
                    tp = precio + (2.5 * atr)
                    msg = (f"📐 *RADAR FIBONACCI: {ticker}*\n\n"
                           f"El precio corrigió exactamente hasta el nivel {nivel} del último impulso.\n"
                           f"💵 *Precio:* ${precio:.2f} | 🔴 *SL:* ${sl:.2f} | 🔵 *TP:* ${tp:.2f}")
                    enviar_telegram(msg)

            # --- RADAR 2: COMPRESIÓN BOLLINGER + MACD ---
            compresion_extrema = float(ultimo["BB_Width"]) < 0.05 # Bandas súper estrechas (menos de 5% de ancho)
            cruce_macd_alcista = float(ultimo["MACD"]) > float(ultimo["MACD_Signal"]) and float(df.iloc[-2]["MACD"]) <= float(df.iloc[-2]["MACD_Signal"])
            
            if compresion_extrema and cruce_macd_alcista:
                sl = precio - (1.5 * atr)
                tp = precio + (3.0 * atr) # Buscamos una explosión más larga
                msg = (f"💥 *RADAR BOLLINGER/MACD: {ticker}*\n\n"
                       f"Compresión extrema de volatilidad detectada y el MACD acaba de dar cruce alcista (explosión inminente).\n"
                       f"💵 *Precio:* ${precio:.2f} | 🔴 *SL:* ${sl:.2f} | 🔵 *TP:* ${tp:.2f}")
                enviar_telegram(msg)
                
        except Exception as e:
            print(f"Error en {ticker}: {e}")

def radar_bonos():
    print("Radar 3: Escaneando Arbitraje de Bonos...")
    # Ejemplo de par clásico para medir desarbitraje en pesos
    par = ("AL35.BA", "TX26.BA") 
    try:
        df1 = yf.download(par[0], period="3mo", interval="1d", progress=False)
        df2 = yf.download(par[1], period="3mo", interval="1d", progress=False)
        
        if not df1.empty and not df2.empty:
            if isinstance(df1.columns, pd.MultiIndex): df1.columns = df1.columns.get_level_values(0)
            if isinstance(df2.columns, pd.MultiIndex): df2.columns = df2.columns.get_level_values(0)
            
            # Calculamos el Ratio (AL35 / TX26)
            ratio = df1["Close"] / df2["Close"]
            
            # RSI del Ratio (14 días)
            delta = ratio.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_ratio = 100 - (100 / (1 + rs))
            
            ultimo_rsi = float(rsi_ratio.iloc[-1])
            
            if ultimo_rsi < 30:
                msg = (f"⚖️ *RADAR ARBITRAJE BONOS*\n\n"
                       f"Desarbitraje extremo detectado entre {par[0]} y {par[1]}.\n"
                       f"El ratio está sobrevendido (RSI Ratio: {ultimo_rsi:.1f}). {par[0]} está muy barato en relación a {par[1]}.")
                enviar_telegram(msg)
            elif ultimo_rsi > 70:
                msg = (f"⚖️ *RADAR ARBITRAJE BONOS*\n\n"
                       f"Desarbitraje extremo detectado entre {par[0]} y {par[1]}.\n"
                       f"El ratio está sobrecomprado (RSI Ratio: {ultimo_rsi:.1f}). {par[0]} está muy caro en relación a {par[1]}.")
                enviar_telegram(msg)
                
    except Exception as e:
        print(f"Error en Bonos: {e}")

if __name__ == "__main__":
    radar_acciones()
    radar_bonos()
    print("Radares apagados.")
