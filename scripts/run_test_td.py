import ccxt
import pandas as pd
import talib
import numpy as np

def fetch_data(symbol='SOL/USDT', timeframe='1h', limit=9000):
    exchange = ccxt.binance()
    # Obtenemos las velas: [timestamp, open, high, low, close, volume]
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    print(df)
    return df

def analyze_patterns(df):
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values

    # 1. Indicadores de tendencia e impulso
    df['RSI'] = talib.RSI(close, timeperiod=14)
    df['EMA_20'] = talib.EMA(close, timeperiod=20)
    upper, mid, lower = talib.BBANDS(close, timeperiod=20)

    # 2. Reconocimiento de Patrones de Velas (Retorna > 0 alcista, < 0 bajista)
    df['Engulfing'] = talib.CDLENGULFING(df['open'], high, low, close)
    df['Hammer'] = talib.CDLHAMMER(df['open'], high, low, close)

    print(df)
    return df


def ai_agent_decision(row):
    # El agente evalúa la última fila del DataFrame
    score = 0

    if row['RSI'] < 30: score += 1
    if row['Engulfing'] > 0: score += 2
    if row['close'] > row['EMA_20']: score += 1

    # Decisión final
    if score >= 3:
        return "BUY"
    elif row['RSI'] > 75 or row['Engulfing'] < 0:
        return "SELL"
    return "HOLD"


if __name__ == "__main__":
    # 1. Obtener y analizar datos
    df = fetch_data()
    df_analizado = analyze_patterns(df)

    # 2. Guardar el DataFrame en un archivo (Formato CSV es mejor para datos)
    # Si prefieres texto plano, usamos df.to_string()
    with open("data.txt", "w", encoding='utf-8') as archivo:
        archivo.write(df_analizado.to_string())

    # 3. Extraer la última fila para el Agente de IA
    ultima_vela = df_analizado.iloc[-1]

    # 4. Obtener decisión
    decision = ai_agent_decision(ultima_vela)

    print(f"\n--- REPORTE DEL AGENTE ---")
    print(f"Estado actual de SOL: {ultima_vela['close']} USDT")
    print(f"RSI: {ultima_vela['RSI']:.2f}")
    print(f"Decisión del Agente: {decision}")