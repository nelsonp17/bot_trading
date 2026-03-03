def is_high_volume(ticker, min_volume_usd=1000000):
    """"El Volumen de 24 Horas (Filtro Inicial)
        Es la métrica más básica. Si una moneda mueve menos de $1,000,000 USD al día,
        suele considerarse de baja liquidez para un bot que opere con montos significativos.
    """
    # 'quoteVolume' en Binance para pares USDT es el volumen en dólares
    volume = ticker.get('quoteVolume', 0)
    return volume >= min_volume_usd

def get_spread_percentage(ticker):
    """ El Spread (Costo de Entrada/Salida) El Spread es la diferencia entre el precio de
        venta más bajo (Ask) y el precio de compra más alto (Bid).
        Un spread alto indica baja liquidez.
        Fórmula: Desaparramar %= (Ask - Bid) / Ask * 100
        Umbral: Para una moneda de alta liquidez, el spread debería ser menor al 0.05% - 0.10%
    """
    ask = ticker['ask']
    bid = ticker['bid']
    if ask and bid:
        spread = (ask - bid) / ask * 100
        return round(spread, 4)
    return 100 # Inoperable si no hay datos

def check_liquidity_depth(exchange, symbol, target_usd=5000):
    """
    Verifica si podemos comprar/vender 'target_usd' sin mover el precio más del 1%
    """
    order_book = exchange.fetch_order_book(symbol)
    bids = order_book['bids'] # Compradores
    asks = order_book['asks'] # Vendedores

    accumulated_usd = 0
    for price, amount in asks: # Para compra (viendo el lado de la venta)
        accumulated_usd += (price * amount)
        # Si el precio actual de la orden es > 1% del precio mejor ask, paramos
        if price > asks[0][0] * 1.01:
            break
        if accumulated_usd >= target_usd:
            return True # Hay suficiente profundidad

    return False