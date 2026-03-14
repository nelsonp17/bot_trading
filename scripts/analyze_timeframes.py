#!/usr/bin/env python3
"""
Script de Análisis de Timeframes

Analiza múltiples timeframes para un símbolo y usa la IA para determinar
cuáles son los más óptimos para operar.

Usage:
    python scripts/analyze_timeframes.py --symbol BTC/USDT
    python scripts/analyze_timeframes.py --symbol BTC/USDT ETH/USDT SOL/USDT
    python scripts/analyze_timeframes.py --symbol ALL --output data/timeframes/timeframes_config.json
"""

import sys
import os
import json
import argparse
import ccxt
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.bot.ia.predictor import get_predictor

# Timeframes a analizar
DEFAULT_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

# Cantidad de velas por timeframe
DEFAULT_HISTORY = {"1m": 500, "5m": 500, "15m": 200, "1h": 200, "4h": 100, "1d": 90}


def fetch_multi_timeframe_data(symbol, timeframes, exchange):
    """Descarga datos de múltiples timeframes."""
    data = {}

    print(f"[*] Descargando datos para {symbol}...")

    for tf in timeframes:
        limit = DEFAULT_HISTORY.get(tf, 100)
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            data[tf] = df
            print(f"    ✓ {tf}: {len(df)} velas descargadas")
        except Exception as e:
            print(f"    ✗ {tf}: Error - {e}")

    return data


def calculate_indicators_summary(df, timeframe):
    """Calcula indicadores básicos para un timeframe."""
    if df is None or df.empty:
        return {}

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    close = latest["close"]
    volume = latest["volume"]

    # RSI simple
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = rsi.iloc[-1] if not rsi.empty else 50

    # Volatilidad
    volatility = df["close"].pct_change().rolling(14).std() * 100

    # Tendencia
    ema_9 = df["close"].ewm(span=9, adjust=False).mean()
    ema_21 = df["close"].ewm(span=21, adjust=False).mean()
    trend = "ALCISTA" if ema_9.iloc[-1] > ema_21.iloc[-1] else "BAJISTA"

    return {
        "timeframe": timeframe,
        "price": float(close),
        "change_1h": float((close - df["close"].iloc[-4]) / df["close"].iloc[-4] * 100)
        if len(df) >= 4
        else 0,
        "volume": float(volume),
        "rsi": float(rsi_val),
        "volatility": float(volatility.iloc[-1]) if not volatility.empty else 0,
        "trend": trend,
        "ema_9": float(ema_9.iloc[-1]),
        "ema_21": float(ema_21.iloc[-1]),
    }


def analyze_with_ia(symbol, data_summary, provider):
    """Usa la IA para determinar los timeframes óptimos."""
    predictor = get_predictor(provider)

    prompt = f"""Analiza los siguientes datos de mercado para el símbolo {symbol} 
y determina cuáles timeframes son los MÁS ÓPTIMOS para operar trading.

DATOS POR TIMEFRAME:
{json.dumps(data_summary, indent=2)}

INSTRUCCIONES:
1. Selecciona un timeframe PRIMARY (principal) para el análisis principal
2. Selecciona timeframes SECONDARY (2-3) para confirmación de señales
3. Para cada timeframe, especifica cuántas velas de historial son necesarias (HISTORY)
4. Justifica tu selección basándote en volatilidad, tendencia y volumen

RESPONDE EN JSON:
{{
    "symbol": "{symbol}",
    "primary": {{
        "timeframe": "1h",
        "history": 48,
        "reasoning": "Explicación breve"
    }},
    "secondary": [
        {{"timeframe": "15m", "history": 100, "reasoning": "..."}},
        {{"timeframe": "4h", "history": 30, "reasoning": "..."}}
    ],
    "analysis": {{
        "recommended_strategy": "Breakout/Swing/Scalping",
        "risk_level": "Bajo/Medio/Alto",
        "volatility_assessment": "..."
    }}
}}
"""

    try:
        if provider.lower() == "deepseek":
            from openai import OpenAI

            client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
        else:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            result = response.parsed

        return result
    except Exception as e:
        print(f"[!] Error con IA: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Analiza timeframes óptimos para símbolos usando IA"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        nargs="+",  # Permite múltiples argumentos
        required=True,
        help="Símbolo(s) a analizar (ej. BTC/USDT) o 'ALL' para análisis general",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="gemini",
        choices=["gemini", "deepseek"],
        help="Proveedor de IA",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/timeframes/timeframes_config.json",
        help="Archivo de salida para la configuración",
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        default="1m,5m,15m,1h,4h,1d",
        help="Timeframes a analizar (separados por coma)",
    )
    parser.add_argument(
        "--network",
        type=str,
        default="mainnet",
        choices=["sandbox", "testnet", "mainnet"],
        help="Red de Binance",
    )

    args = parser.parse_args()

    # Determinar símbolos a analizar
    if args.symbol[0].upper() == "ALL":
        symbols = [
            "BTC/USDT",
            "ETH/USDT",
            "BNB/USDT",
            "SOL/USDT",
            "XRP/USDT",
            "ADA/USDT",
        ]
    else:
        symbols = args.symbol  # Ya es una lista

    timeframes = [t.strip() for t in args.timeframes.split(",")]

    # Inicializar exchange
    use_testnet = args.network in ["sandbox", "testnet"]
    exchange = ccxt.binance({"enableRateLimit": True})
    if use_testnet:
        exchange.set_sandbox_mode(True)

    # Cargar timeframes existentes si existen
    config = {}
    if os.path.exists(args.output):
        with open(args.output, "r") as f:
            config = json.load(f)

    print("=" * 60)
    print(f"  ANÁLISIS DE TIMEFRAMES - {args.provider.upper()}")
    print("=" * 60)

    for symbol in symbols:
        print(f"\n[*] Analizando {symbol}...")

        # Descargar datos
        data = fetch_multi_timeframe_data(symbol, timeframes, exchange)

        if not data:
            print(f"[!] No se pudieron obtener datos para {symbol}")
            continue

        # Calcular resumen de indicadores
        summary = {}
        for tf, df in data.items():
            summary[tf] = calculate_indicators_summary(df, tf)

        # Analizar con IA
        print(f"[*] Consultando a {args.provider}...")
        result = analyze_with_ia(symbol, summary, args.provider)

        if result:
            print(f"\n[✓] RESULTADO PARA {symbol}:")
            print(f"    Primary: {result.get('primary', {}).get('timeframe', 'N/A')}")
            print(
                f"    Secondary: {[s.get('timeframe') for s in result.get('secondary', [])]}"
            )
            print(
                f"    Estrategia: {result.get('analysis', {}).get('recommended_strategy', 'N/A')}"
            )

            # Guardar en configuración
            config[symbol] = {
                "primary": result.get("primary", {}),
                "secondary": result.get("secondary", []),
                "analysis": result.get("analysis", {}),
                "all_timeframes_summary": summary,
            }
        else:
            print(f"[!] No se pudo completar el análisis para {symbol}")

    # Guardar configuración
    with open(args.output, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n[✓] Configuración guardada en {args.output}")
    print("\nUso en el bot:")
    print(f"  python scripts/run_trading_bot.py --symbol {symbols[0]} --budget 100")


if __name__ == "__main__":
    main()
