import sys
import os
import argparse

# Añadir la raíz del proyecto al sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.bot.trading_bot import TradingBot

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot de Trading con IA")
    parser.add_argument("--provider", type=str, default="gemini", choices=["gemini", "deepseek"], help="Proveedor IA")
    parser.add_argument("--symbol", type=str, default="BTC/USDT", help="Par de trading")
    parser.add_argument("--timeframe", type=str, default="1h", help="Timeframe")
    parser.add_argument("--amount", type=float, default=10.0, help="USDT por operación (Fallback)")
    parser.add_argument("--budget", type=float, help="Presupuesto TOTAL asignado al bot")
    parser.add_argument("--min-price", type=float, default=0.0, help="Precio Mínimo")
    parser.add_argument("--max-price", type=float, default=999999.0, help="Precio Máximo")
    parser.add_argument("--network", type=str, default="sandbox", choices=["sandbox", "testnet", "mainnet", "demo"],
                        help="Red de operación: sandbox, testnet, mainnet o demo")

    args = parser.parse_args()

    bot = TradingBot(
        provider=args.provider,
        symbol=args.symbol,
        timeframe=args.timeframe,
        amount=args.amount,
        budget=args.budget,
        min_price=args.min_price,
        max_price=args.max_price,
        network=args.network
    )
    bot.run()
