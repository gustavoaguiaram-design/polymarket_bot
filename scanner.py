"""
Scanner Polymarket — busca mercados BTC Up/Down 5min em tempo real
Usa apenas APIs públicas (sem autenticação necessária)
"""
import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Optional

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API  = "https://clob.polymarket.com"

async def get_btc_5min_markets(session: aiohttp.ClientSession) -> list:
    """Busca mercados BTC Up/Down de 5 minutos ativos"""
    try:
        params = {
            "active": "true",
            "closed": "false",
            "limit": 100,
            "tag_slug": "crypto"
        }
        async with session.get(f"{GAMMA_API}/markets", params=params) as r:
            if r.status != 200:
                return []
            data = await r.json()

        markets = data if isinstance(data, list) else data.get("markets", [])

        # Filtra mercados BTC 5min
        btc_markets = []
        for m in markets:
            question = m.get("question", "").lower()
            if ("btc" in question or "bitcoin" in question) and (
                "5" in question or "five" in question
            ) and ("up" in question or "higher" in question or "above" in question):
                btc_markets.append({
                    "id": m.get("id"),
                    "question": m.get("question"),
                    "conditionId": m.get("conditionId"),
                    "clobTokenIds": m.get("clobTokenIds"),
                    "endDate": m.get("endDate"),
                    "outcomePrices": m.get("outcomePrices"),
                    "volume": m.get("volume"),
                })

        return btc_markets
    except Exception as e:
        print(f"[Scanner] Erro buscar mercados: {e}")
        return []


async def get_orderbook(session: aiohttp.ClientSession, token_id: str) -> Optional[dict]:
    """Busca orderbook de um token específico"""
    try:
        async with session.get(f"{CLOB_API}/book", params={"token_id": token_id}) as r:
            if r.status != 200:
                return None
            return await r.json()
    except:
        return None


async def get_btc_price_binance(session: aiohttp.ClientSession) -> Optional[float]:
    """Busca preço atual do BTC na Binance (grátis, sem auth)"""
    try:
        async with session.get(
            "https://fapi.binance.com/fapi/v1/ticker/price",
            params={"symbol": "BTCUSDT"}
        ) as r:
            data = await r.json()
            return float(data["price"])
    except:
        return None


async def get_btc_klines(session: aiohttp.ClientSession, limit: int = 10) -> list:
    """Busca candles BTC 1min para detectar momentum"""
    try:
        async with session.get(
            "https://fapi.binance.com/fapi/v1/klines",
            params={"symbol": "BTCUSDT", "interval": "1m", "limit": limit}
        ) as r:
            data = await r.json()
            return [{"close": float(c[4]), "volume": float(c[5])} for c in data]
    except:
        return []


if __name__ == "__main__":
    async def test():
        async with aiohttp.ClientSession() as session:
            print("=== TESTE SCANNER POLYMARKET ===\n")

            price = await get_btc_price_binance(session)
            print(f"BTC atual: ${price:,.2f}")

            klines = await get_btc_klines(session, 5)
            if klines:
                move = (klines[-1]["close"] - klines[0]["close"]) / klines[0]["close"] * 100
                print(f"Movimento 5min: {move:+.3f}%")

            print("\nBuscando mercados BTC 5min no Polymarket...")
            markets = await get_btc_5min_markets(session)
            if markets:
                print(f"Encontrados: {len(markets)} mercados")
                for m in markets[:3]:
                    print(f"  → {m['question']}")
                    print(f"    Odds: {m.get('outcomePrices')}")
            else:
                print("Nenhum mercado BTC 5min ativo encontrado agora")
                print("(Normal — esses mercados abrem a cada 5min)")

    asyncio.run(test())
