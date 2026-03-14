python scripts/analyze_timeframes.py --symbol BTC/USDT ETH/USDT SOL/USDT --provider deepseek --network=mainnet

python scripts/run_market_scanner_bot.py --capital 500 --quote USDT --provider deepseek --mode volume --type both


python scripts/run_trading_bot.py --symbol NEAR/USDT:USDT --budget 500 --market_type future --provider deepseek --scan_id SCAN_20260313_210105 --network testnet