import pandas as pd
import numpy as np


def calculate_rsi(prices, period=14):
    """
    Calcula el Relative Strength Index (RSI).

    Args:
        prices: Serie de precios de cierre
        period: Período para el cálculo (default 14)

    Returns:
        Serie con valores RSI
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_ema(prices, period):
    """
    Calcula la Exponential Moving Average (EMA).

    Args:
        prices: Serie de precios de cierre
        period: Período para el cálculo

    Returns:
        Serie con valores EMA
    """
    return prices.ewm(span=period, adjust=False).mean()


def calculate_sma(prices, period):
    """
    Calcula la Simple Moving Average (SMA).

    Args:
        prices: Serie de precios de cierre
        period: Período para el cálculo

    Returns:
        Serie con valores SMA
    """
    return prices.rolling(window=period).mean()


def calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9):
    """
    Calcula el MACD (Moving Average Convergence Divergence).

    Args:
        prices: Serie de precios de cierre
        fast_period: Período rápido (default 12)
        slow_period: Período lento (default 26)
        signal_period: Período de señal (default 9)

    Returns:
        DataFrame con 'macd', 'signal' y 'histogram'
    """
    ema_fast = calculate_ema(prices, fast_period)
    ema_slow = calculate_ema(prices, slow_period)

    macd = ema_fast - ema_slow
    signal = calculate_ema(macd, signal_period)
    histogram = macd - signal

    return pd.DataFrame({"macd": macd, "signal": signal, "histogram": histogram})


def calculate_atr(high, low, close, period=14):
    """
    Calcula el Average True Range (ATR).

    Args:
        high: Serie de precios altos
        low: Serie de precios bajos
        close: Serie de precios de cierre
        period: Período para el cálculo (default 14)

    Returns:
        Serie con valores ATR
    """
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def calculate_bollinger_bands(prices, period=20, num_std=2):
    """
    Calcula las Bandas de Bollinger.

    Args:
        prices: Serie de precios de cierre
        period: Período para el cálculo (default 20)
        num_std: Número de desviaciones estándar (default 2)

    Returns:
        DataFrame con 'upper', 'middle' y 'lower'
    """
    middle = calculate_sma(prices, period)
    std = prices.rolling(window=period).std()

    upper = middle + (std * num_std)
    lower = middle - (std * num_std)

    return pd.DataFrame({"upper": upper, "middle": middle, "lower": lower})


def calculate_stochastic(high, low, close, period=14, smooth_k=3, smooth_d=3):
    """
    Calcula el Oscilador Estocástico.

    Args:
        high: Serie de precios altos
        low: Serie de precios bajos
        close: Serie de precios de cierre
        period: Período %K (default 14)
        smooth_k: Suavizado %K (default 3)
        smooth_d: Suavizado %D (default 3)

    Returns:
        DataFrame con 'k' y 'd'
    """
    lowest_low = low.rolling(window=period).min()
    highest_high = high.rolling(window=period).max()

    k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    d = k.rolling(window=smooth_d).mean()

    return pd.DataFrame({"k": k, "d": d})


def calculate_obv(close, volume):
    """
    Calcula el On-Balance Volume (OBV).

    Args:
        close: Serie de precios de cierre
        volume: Serie de volúmenes

    Returns:
        Serie con valores OBV
    """
    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    return obv


def add_all_indicators(df):
    """
    Agrega todos los indicadores técnicos al DataFrame.

    Args:
        df: DataFrame con columnas 'open', 'high', 'low', 'close', 'volume'

    Returns:
        DataFrame con indicadores adicionales
    """
    result = df.copy()

    close = result["close"]
    high = result["high"]
    low = result["low"]
    volume = result["volume"]

    result["rsi_14"] = calculate_rsi(close, 14)
    result["rsi_21"] = calculate_rsi(close, 21)

    result["ema_9"] = calculate_ema(close, 9)
    result["ema_21"] = calculate_ema(close, 21)
    result["ema_50"] = calculate_ema(close, 50)
    result["ema_200"] = calculate_ema(close, 200)

    result["sma_20"] = calculate_sma(close, 20)
    result["sma_50"] = calculate_sma(close, 50)
    result["sma_200"] = calculate_sma(close, 200)

    macd = calculate_macd(close)
    result["macd"] = macd["macd"]
    result["macd_signal"] = macd["signal"]
    result["macd_histogram"] = macd["histogram"]

    result["atr_14"] = calculate_atr(high, low, close, 14)

    bb = calculate_bollinger_bands(close)
    result["bb_upper"] = bb["upper"]
    result["bb_middle"] = bb["middle"]
    result["bb_lower"] = bb["lower"]
    result["bb_position"] = (close - bb["lower"]) / (bb["upper"] - bb["lower"])

    stoch = calculate_stochastic(high, low, close)
    result["stoch_k"] = stoch["k"]
    result["stoch_d"] = stoch["d"]

    result["obv"] = calculate_obv(close, volume)

    result["volume_ma_20"] = calculate_sma(volume, 20)
    result["volume_ratio"] = volume / result["volume_ma_20"]

    result["price_change_1h"] = close.pct_change(1) * 100
    result["price_change_4h"] = close.pct_change(4) * 100
    result["price_change_24h"] = close.pct_change(24) * 100

    result["volatility_20"] = close.pct_change().rolling(20).std() * 100

    return result


def get_indicators_summary(df):
    """
    Genera un resumen de los indicadores actuales para enviar a la IA.

    Args:
        df: DataFrame con indicadores calculados

    Returns:
        String con el resumen
    """
    latest = df.iloc[-1]

    summary = f"""
INDICADORES TÉCNICOS ACTUALES:
==============================
PRECIO ACTUAL: {latest["close"]:.8f}

MEDIAS MÓVILES:
- EMA 9: {latest.get("ema_9", "N/A"):.8f}
- EMA 21: {latest.get("ema_21", "N/A"):.8f}
- EMA 50: {latest.get("ema_50", "N/A"):.8f}
- EMA 200: {latest.get("ema_200", "N/A"):.8f}
- SMA 20: {latest.get("sma_20", "N/A"):.8f}

RSI (14): {latest.get("rsi_14", "N/A"):.2f}
RSI (21): {latest.get("rsi_21", "N/A"):.2f}

MACD:
- MACD: {latest.get("macd", "N/A"):.8f}
- Signal: {latest.get("macd_signal", "N/A"):.8f}
- Histogram: {latest.get("macd_histogram", "N/A"):.8f}

ATR (14): {latest.get("atr_14", "N/A"):.8f}

BOLLINGER BANDS:
- Upper: {latest.get("bb_upper", "N/A"):.8f}
- Middle: {latest.get("bb_middle", "N/A"):.8f}
- Lower: {latest.get("bb_lower", "N/A"):.8f}
- Position: {latest.get("bb_position", "N/A"):.2%}

ESTOCÁSTICO:
- %K: {latest.get("stoch_k", "N/A"):.2f}
- %D: {latest.get("stoch_d", "N/A"):.2f}

VOLUMEN:
- Ratio vs MA20: {latest.get("volume_ratio", "N/A"):.2f}

CAMBIO DE PRECIO:
- 1h: {latest.get("price_change_1h", "N/A"):+.2f}%
- 4h: {latest.get("price_change_4h", "N/A"):+.2f}%
- 24h: {latest.get("price_change_24h", "N/A"):+.2f}%

VOLATILIDAD (20): {latest.get("volatility_20", "N/A"):.2f}%
"""
    return summary


def get_signal_from_indicators(df):
    """
    Genera una señal básica basada en indicadores técnicos.

    Args:
        df: DataFrame con indicadores calculados

    Returns:
        String con la señal: 'COMPRA', 'VENTA', 'NEUTRAL'
    """
    latest = df.iloc[-1]

    signals = []

    rsi = latest.get("rsi_14")
    if rsi:
        if rsi < 30:
            signals.append("COMPRA")  # Sobrevendido
        elif rsi > 70:
            signals.append("VENTA")  # Sobrecomprado

    ema_9 = latest.get("ema_9")
    ema_21 = latest.get("ema_21")
    if ema_9 and ema_21:
        if ema_9 > ema_21:
            signals.append("COMPRA")
        else:
            signals.append("VENTA")

    macd = latest.get("macd")
    macd_signal = latest.get("macd_signal")
    if macd and macd_signal:
        if macd > macd_signal:
            signals.append("COMPRA")
        else:
            signals.append("VENTA")

    bb_position = latest.get("bb_position")
    if bb_position:
        if bb_position < 0.2:
            signals.append("COMPRA")  # Cerca de la banda inferior
        elif bb_position > 0.8:
            signals.append("VENTA")  # Cerca de la banda superior

    compra_count = signals.count("COMPRA")
    venta_count = signals.count("VENTA")

    if compra_count > venta_count + 1:
        return "COMPRA"
    elif venta_count > compra_count + 1:
        return "VENTA"
    elif compra_count > 0:
        return "NEUTRAL"
    else:
        return "NEUTRAL"
