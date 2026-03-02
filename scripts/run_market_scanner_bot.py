import sys
import os
import argparse

# Añadir la raíz del proyecto al sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.bot.market_scanner_bot import MarketScanner

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Escáner de Mercado con IA")
    parser.add_argument("--provider", type=str, default="gemini", choices=["gemini", "deepseek"], help="Proveedor IA")
    parser.add_argument("--capital", type=float, default=100.0, help="Capital total a invertir")
    parser.add_argument("--quote", type=str, default="USDT", help="Par base (USDT, USDC, BTC)")
    parser.add_argument("--mode", type=str, default="volume", choices=["volume", "volatility"],
                        help="Modo de selección: volume o volatility")
    parser.add_argument("--symbol", type=str, default=None, help="Símbolo específico a consultar (ej. BTC/USDT)")
    parser.add_argument("--type", type=str, default="spot", choices=["spot", "future", "both"], help="Tipo de mercado (spot, future o both)")
    parser.add_argument("--num_top", type=int, default=15, help="Número de activos a analizar")

    args = parser.parse_args()

    scanner = MarketScanner(
        provider=args.provider,
        capital=args.capital,
        quote=args.quote,
        mode=args.mode,
        symbol=args.symbol,
        market_type=args.type,
        num_top=args.num_top
    )
    scanner.run_scan()
