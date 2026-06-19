"""
Configuração do Polymarket Flow Bot
"""
import os
from dotenv import load_dotenv
load_dotenv()

# ─── Polymarket ────────────────────────────────────────────
CLOB_API  = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_WS   = "wss://clob.polymarket.com/ws"

# ─── Wallet ────────────────────────────────────────────────
POLY_PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
POLY_FUNDER      = os.getenv("POLY_FUNDER", "")

# ─── Binance (dados BTC) ───────────────────────────────────
BINANCE_WS  = "wss://fstream.binance.com/ws/btcusdt@kline_1m"
BINANCE_API = "https://fapi.binance.com"

# ─── Estratégia ────────────────────────────────────────────
MIN_ORDER_SIZE_USD = 500.0
MIN_EDGE           = 0.03
BET_SIZE_USD       = 2.0            # $2 por trade
MAX_POSITIONS      = 20             # 20 simultâneos
MIN_ODDS           = 0.30
MAX_ODDS           = 0.70

# ─── Paper trading ─────────────────────────────────────────
PAPER_TRADING = True
PAPER_BALANCE = 500.0

# ─── API ───────────────────────────────────────────────────
API_PORT = 8001
