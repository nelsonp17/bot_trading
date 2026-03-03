import sys
import os
import argparse

# Añadir la raíz del proyecto al sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.bot.trading_bot import TradingBot

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot de Trading con IA (Modo Cerebro vs Músculo)")
    parser.add_argument("--provider", type=str, default="gemini", choices=["gemini", "deepseek"], help="Proveedor IA")
    parser.add_argument("--symbol", type=str, default="BTC/USDT", help="Par de trading")
    parser.add_argument("--timeframe", type=str, default="1h", help="Timeframe de velas")
    parser.add_argument("--budget", type=float, required=True, help="Presupuesto TOTAL que la IA tiene permitido gestionar")
    parser.add_argument("--network", type=str, default="sandbox", choices=["sandbox", "testnet", "mainnet", "demo"],
                        help="Red de operación: sandbox, testnet, mainnet o demo")
    parser.add_argument("--market_type", type=str, default="spot", choices=["spot", "future"], help="Tipo de mercado (spot o future)")
    parser.add_argument("--scan_id", type=str, default=None, help="ID específico del escaneo a utilizar")
    parser.add_argument("--run_script_id", type=str, default=None, help="ID específico del run script a utilizar")

    args = parser.parse_args()

    # El bot ahora solo recibe el budget y el contexto de red/mercado.
    # Los precios y montos de operación los decidirá la IA en el Plan de Ejecución.
    bot = TradingBot(
        provider=args.provider,
        symbol=args.symbol,
        timeframe=args.timeframe,
        budget=args.budget,
        network=args.network,
        market_type=args.market_type,
        scan_id=args.scan_id,
        run_script_id=args.run_script_id
    )
    bot.run()
