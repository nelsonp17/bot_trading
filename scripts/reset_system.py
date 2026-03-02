import os
import time
import sqlite3
from binance.client import Client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def reset_testnet():
    print("="*50)
    print("🚀 REINICIANDO SISTEMA DE TRADING (TESTNET)")
    print("="*50)

    # 1. Configurar Cliente de Binance
    api_key = os.getenv("BINANCE_TESTNET_API_KEY")
    secret_key = os.getenv("BINANCE_TESTNET_SECRET_KEY")

    if not api_key or not secret_key:
        print("[!] Error: No se encontraron las llaves API de TESTNET en el .env")
        return

    client = Client(api_key, secret_key, testnet=True)

    # 2. Liquidar activos a USDT
    print("[*] 1. Liquidando activos en el Exchange...")
    try:
        account = client.get_account()
        balances = account.get('balances', [])
        
        for asset in balances:
            symbol = asset['asset']
            free = float(asset['free'])
            
            if free > 0 and symbol != 'USDT' and symbol != 'BNB':
                pair = f"{symbol}USDT"
                try:
                    # Verificar si el par existe y obtener filtros
                    info = client.get_symbol_info(pair)
                    if not info: continue
                    
                    print(f"    [>] Vendiendo {free} {symbol}...")
                    
                    # Ajustar cantidad según filtros de Binance
                    step_size = 0.00000001
                    for f in info['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            step_size = float(f['stepSize'])
                    
                    import math
                    precision = len(str(step_size).split('.')[-1].rstrip('0'))
                    quantity = math.floor(free * (10**precision)) / (10**precision)

                    if quantity > 0:
                        client.order_market_sell(symbol=pair, quantity=quantity)
                        print(f"    [+] {symbol} liquidado con éxito.")
                except Exception as e:
                    print(f"    [!] No se pudo vender {symbol}: {e}")

    except Exception as e:
        print(f"[!] Error al acceder a la cuenta: {e}")

    # 3. Limpiar Base de Datos Local
    print("[*] 2. Limpiando Base de Datos local (SQLite)...")
    db_path = "db.db"
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            tables = ['trades', 'predictions', 'market_scans', 'execution_plans']
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
                print(f"    [-] Tabla '{table}' vaciada.")
            
            conn.commit()
            conn.close()
            print("[+] Base de datos reseteada correctamente.")
        except Exception as e:
            print(f"[!] Error al limpiar DB: {e}")
    else:
        print("[?] No se encontró el archivo db.db.")

    # 4. Mostrar Saldo Final
    print("[*] 3. Estado Final del Balance:")
    try:
        usdt_balance = client.get_asset_balance(asset='USDT')
        print(f"    >> SALDO TOTAL: {usdt_balance['free']} USDT")
    except: pass
    
    print("[*] " + "="*50)
    print("✨ Reinicio completado. El sistema está limpio para operar.")
    print("="*50)

if __name__ == "__main__":
    reset_testnet()
