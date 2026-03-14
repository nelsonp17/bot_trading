import pandas as pd

def generar_resumen_para_ia(csv_path):
    df = pd.read_csv(csv_path)
    
    # 1. Análisis de Volatilidad
    volatilidad_avg = (df['High'] - df['Low']).mean() / df['Close'].mean() * 100
    
    # 2. Correlación de Señales (Ejemplo con tu Fib 61.8)
    hits_fib = df[df['feat_dist_fib618'] <= 0]
    win_rate_fib = (hits_fib['target_return_4h'] > 0).mean() * 100
    avg_ret_fib = hits_fib['target_return_4h'].mean() * 100

    # 3. Tendencia Macro (SMA 1D)
    bull_market_time = (df['feat_dist_sma1d'] > 0).mean() * 100
    
    # CONSTRUIR EL PROMPT
    resumen = f"""
    CONTEXTO DE MERCADO (ÚLTIMOS 3 MESES):
    - Activo: BTC/USDT
    - Volatilidad Promedio (15m): {volatilidad_avg:.2f}%
    - Tiempo en Tendencia Alcista (D1): {bull_market_time:.1f}% del periodo.
    
    COMPORTAMIENTO DE INDICADORES:
    - Señal Fib 61.8%: Win Rate de {win_rate_fib:.1f}% con retorno promedio de {avg_ret_fib:.2f}% a 4h.
    - RSI 1H Promedio: {df['feat_rsi_1h'].mean():.2f}
    
    MÁXIMOS Y MÍNIMOS:
    - Max Drawdown en el periodo: {df['target_return_4h'].min()*100:.2f}%
    - Max Upside potencial: {df['target_return_4h'].max()*100:.2f}%
    """
    return resumen

# Uso:
# print(generar_resumen_para_ia("data_estudio_mercado.csv"))

if __name__ == "__main__":
    print(generar_resumen_para_ia("data_estudio_mercado.csv"))
