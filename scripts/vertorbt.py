import vectorbt as vbt
import pandas as pd
import pandas_ta as ta
import ccxt

# ============================================================
# 1. Descarga Masiva de Datos (3 Meses / 90 Días)
# ============================================================

def fetch_3_months_data(symbol='SOL/USDT', timeframe='15m'):
    exchange = ccxt.binance({'enableRateLimit': True,'options': {'defaultType': 'spot'}})
    
    # Calcular milisegundos para 90 días aprox
    target_candles = 90 * 24 * 4  # 8640 velas
    # Restamos el tiempo necesario desde "ahora"
    since = exchange.milliseconds() - (target_candles * 15 * 60 * 1000)
    
    all_ohlcv = []
    print(f"[*] Iniciando descarga de 3 meses para {symbol}...")
    
    while len(all_ohlcv) < target_candles:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since, limit=1000)
        if not batch: break
        all_ohlcv.extend(batch)
        since = batch[-1][0] + (15 * 60 * 1000)
        print(f"  → Progreso: {len(all_ohlcv)}/{target_candles} velas", end='\r')
        
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    return df

# ============================================================
# 2. Generación de Features (Data Cruda para la IA)
# ============================================================

def prepare_data_for_ai(df):
    # Copiamos para no mutar el original
    data = df.copy()

    # --- 1D Context (Tendencia Macro) ---
    d1_resample = data['Close'].resample('1D').last()
    d1_sma = ta.sma(d1_resample, length=20).reindex(data.index, method='ffill')
    data['feat_dist_sma1d'] = (data['Close'] - d1_sma) / d1_sma

    # --- 4H Context (Fuerza de Tendencia) ---
    res_4h = data.resample('4h').agg({'High':'max', 'Low':'min', 'Close':'last'})
    adx_4h = ta.adx(res_4h['High'], res_4h['Low'], res_4h['Close'])['ADX_14']
    data['feat_adx_4h'] = adx_4h.reindex(data.index, method='ffill')
    data['feat_adx_trend'] = data['feat_adx_4h'].diff()

    # --- 1H Context (Momentum) ---
    h1_close = data['Close'].resample('1h').last().reindex(data.index, method='ffill')
    data['feat_rsi_1h'] = ta.rsi(h1_close, length=14)

    # --- 15M (Nivel de Precio) ---
    roll_max = data['High'].rolling(window=100).max()
    roll_min = data['Low'].rolling(window=100).min()
    fib_618 = roll_max - ((roll_max - roll_min) * 0.618)
    data['feat_dist_fib618'] = (data['Close'] - fib_618) / fib_618

    # --- TARGET (Lo que la IA debe aprender a predecir) ---
    # Retorno en las próximas 4 horas (16 velas de 15m)
    data['target_return_4h'] = data['Close'].shift(-16) / data['Close'] - 1
    
    return data.dropna()

# ============================================================
# 3. Ejecución
# ============================================================

if __name__ == "__main__":
    raw_data = fetch_3_months_data()
    processed_data = prepare_data_for_ai(raw_data)
    
    # Lógica de señales para el backtest de control
    # Nota: Estos filtros son los que la IA debería optimizar después
    entries = (processed_data['feat_dist_fib618'] <= 0) & (processed_data['feat_rsi_1h'] < 60)
    exits = (processed_data['feat_rsi_1h'] > 70)
    
    pf = vbt.Portfolio.from_signals(
        close=processed_data['Close'],
        entries=entries,
        exits=exits,
        sl_stop=0.02,
        tp_stop=0.04,
        fees=0.001,
        freq='15min'
    )
    
    # Cálculo manual del Benchmark para evitar errores de atributo
    bench_return = (processed_data['Close'].iloc[-1] / processed_data['Close'].iloc[0]) - 1

    print("\n" + "="*40)
    print("RESUMEN DE ESTUDIO (3 MESES)")
    print("="*40)
    print(f"Retorno Estrategia: {pf.total_return()*100:.2f}%")
    print(f"Retorno BTC (Hold): {bench_return*100:.2f}%")
    print(f"Win Rate:           {pf.trades.win_rate()*100:.2f}%")
    print(f"Velas procesadas:   {len(processed_data)}")
    
    # Guardar CSV
    processed_data.to_csv("data_estudio_mercado.csv")
    print("\n[✓] Archivo 'data_estudio_mercado.csv' generado para la IA.")