import sys
import os
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from binance.client import Client
from app.database import get_db_manager
from dotenv import load_dotenv

load_dotenv()


def reset_coin(symbol, market_type="future", network="testnet"):
    """
    Resetea una moneda a 0:
    - Cierra posiciones abiertas en Binance
    - Cancela órdenes pendientes
    - Limpia datos de la base de datos (trades, planes, etc.)
    """

    # Configurar credenciales
    if network == "testnet":
        api_key = os.getenv("BINANCE_FUTURES_TESTNET_API_KEY")
        secret_key = os.getenv("BINANCE_FUTURES_TESTNET_SECRET_KEY")
        use_testnet = True
    elif network == "sandbox":
        api_key = os.getenv("BINANCE_TESTNET_API_KEY")
        secret_key = os.getenv("BINANCE_TESTNET_SECRET_KEY")
        use_testnet = True
    elif network == "demo":
        api_key = os.getenv("BINANCE_DEMO_API_KEY")
        secret_key = os.getenv("BINANCE_DEMO_SECRET_KEY")
        use_testnet = True
    else:  # mainnet
        api_key = os.getenv("BINANCE_API_KEY")
        secret_key = os.getenv("BINANCE_SECRET_KEY")
        use_testnet = False

    client = Client(api_key, secret_key, testnet=use_testnet)
    db = get_db_manager()

    # Normalizar símbolo (quitar / y : para Binance)
    binance_symbol = symbol.replace("/", "").split(":")[0]
    if market_type == "future":
        binance_symbol = binance_symbol  # Binance futures usa FETUSDT

    print(f"\n{'=' * 50}")
    print(f"🔄 RESETEANDO: {symbol} ({market_type})")
    print(f"{'=' * 50}\n")

    # === 1. CERRAR POSICIONES EN BINANCE ===
    if market_type == "future":
        print("[1] Cerrando posiciones en Binance Futures...")
        try:
            positions = client.futures_position_information(symbol=binance_symbol)
            for pos in positions:
                qty = float(pos["positionAmt"])
                if qty != 0:
                    side = "SELL" if qty > 0 else "BUY"
                    print(f"   - Posición encontrada: {qty} {binance_symbol}")
                    print(f"   - Cerrando posición...")
                    try:
                        # Cerrar posición con mercado
                        order = client.futures_create_order(
                            symbol=binance_symbol,
                            side=side,
                            type="MARKET",
                            quantity=abs(qty),
                            reduceOnly=True,
                        )
                        print(f"   ✓ Posición cerrada: {order['orderId']}")
                    except Exception as e:
                        print(f"   ✗ Error cerrando posición: {e}")
                else:
                    print(f"   - Sin posición abierta en {binance_symbol}")
        except Exception as e:
            print(f"   ✗ Error obteniendo posiciones: {e}")

    # === 2. CANCELAR ÓRDENES PENDIENTES ===
    print("\n[2] Cancelando órdenes pendientes...")
    try:
        if market_type == "future":
            orders = client.futures_get_open_orders(symbol=binance_symbol)
        else:
            orders = client.get_open_orders(symbol=binance_symbol)

        if orders:
            for order in orders:
                print(
                    f"   - Cancelando orden: {order['orderId']} ({order['side']} {order['type']})"
                )
                try:
                    if market_type == "future":
                        client.futures_cancel_order(
                            symbol=binance_symbol, orderId=order["orderId"]
                        )
                    else:
                        client.cancel_order(
                            symbol=binance_symbol, orderId=order["orderId"]
                        )
                    print(f"   ✓ Orden cancelada")
                except Exception as e:
                    print(f"   ✗ Error cancelando: {e}")
        else:
            print("   - Sin órdenes pendientes")
    except Exception as e:
        print(f"   ✗ Error cancelando órdenes: {e}")

    # === 3. LIMPIAR BASE DE DATOS ===
    print("\n[3] Limpiando base de datos...")

    # Buscar run_scripts relacionados con este símbolo
    run_scripts = []

    # Obtener todos los run_scripts
    try:
        # SQLite no tiene método directo, necesitamos iterar
        all_trades = db.get_all_trades()
        for trade in all_trades:
            if symbol.replace("/", "") in trade.get("symbol", ""):
                run_scripts.append(trade.get("run_script_id"))
    except:
        pass

    run_scripts = list(set(run_scripts))
    print(f"   - Run scripts encontrados: {len(run_scripts)}")

    # Eliminar trades relacionados
    print("\n[4] Eliminando trades...")
    # Por ahora solo informamos - SQLite no tiene delete fácil sin métodos adicionales
    print("   - Nota: Los trades permanecen en la base de datos (funcionalidad futura)")

    # === 4. MOSTRAR BALANCE FINAL ===
    print("\n[5] Balance final en Binance...")
    try:
        if market_type == "future":
            balances = client.futures_account_balance()
            for b in balances:
                if b["asset"] in ["USDT", symbol.split("/")[0]]:
                    print(f"   - {b['asset']}: {b['balance']}")

            # Verificar posiciones
            positions = client.futures_position_information(symbol=binance_symbol)
            for pos in positions:
                if float(pos["positionAmt"]) != 0:
                    print(
                        f"   ⚠️  Posición restante: {pos['positionAmt']} {binance_symbol}"
                    )
                else:
                    print(f"   ✓ Sin posiciones en {binance_symbol}")
        else:
            balances = client.get_account()["balances"]
            for b in balances:
                if b["asset"] in [symbol.split("/")[0], "USDT"]:
                    print(f"   - {b['asset']}: {b['free']}")
    except Exception as e:
        print(f"   ✗ Error obteniendo balance: {e}")

    print(f"\n{'=' * 50}")
    print(f"✅ RESETEO COMPLETADO para {symbol}")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resetear una moneda a 0")
    parser.add_argument(
        "--symbol", type=str, required=True, help="Símbolo a resetear (ej. FET/USDT)"
    )
    parser.add_argument(
        "--market_type",
        type=str,
        default="future",
        choices=["spot", "future"],
        help="Tipo de mercado",
    )
    parser.add_argument(
        "--network",
        type=str,
        default="testnet",
        choices=["testnet", "sandbox", "demo", "mainnet"],
        help="Red de Binance",
    )

    args = parser.parse_args()

    reset_coin(args.symbol, args.market_type, args.network)
