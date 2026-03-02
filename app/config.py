import os

### Archivo estatico para el bot de trading
BOT_TRADING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app/webhooks/bot_trading_status.json')

# Crear el directorio webhooks si no existe
os.makedirs(os.path.dirname(BOT_TRADING_FILE), exist_ok=True)

# os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'webhooks/bot_status.json')