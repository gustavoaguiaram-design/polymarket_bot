"""
Scanner de fluxo de ordens do Polymarket
Lê o orderbook em tempo real e detecta ordens grandes
"""
import asyncio
import aiohttp
import json
import time
from typing import Optional, Dict, List, Callable
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import CLOB_API, GAMMA_API, CLOB_WS, MIN_ORDER_SIZE_USD


class OrderFlowScanner:
    def __init__(self):
        self.btc_markets: List[dict] = []
        self.orderbooks: Dict[str, dict] = {}
        self.large_orders: List[dict] = []
        self.on_large_order: Optional[Callable] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.stats = {
            "orders_seen": 0,
            "large_orders": 0,
            "markets_tracked": 0,
        }

    async def start(self, on_large_order: Callable):
        self._session = aiohttp.ClientSession()
        self.on_large_order = on_large_order
        self.running = True
        await self._find_btc_markets()
        print(f"[PolyScanner] {len(self.btc_markets)} mercados BTC encontrados")
        asyncio.create_task(self._poll_orderbooks())
        asyncio.create_task(self._refresh_markets_loop())

    async def stop(self):
        self.running = False
        if self._session:
            await self._session.close()

    async def _find_btc_markets(self):
        """Busca mercados BTC ativos no Polymarket"""
        try:
            # Busca mercados via Gamma API
            params = {"active": "true", "closed": "false", "limit": 200}
            async with self._session.get(
                f"{GAMMA_API}/markets", params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status != 200:
                    print(f"[PolyScanner] Gamma API status: {r.status}")
                    return
                data = await r.json()

            markets = data if isinstance(data, list) else data.get("markets", [])

            # Filtra mercados BTC/crypto de curto prazo
            btc = []
            for m in markets:
                q = m.get("question", "").lower()
                tags = [t.get("slug","") for t in m.get("tags", [])]
                is_crypto = "crypto" in tags or "btc" in q or "bitcoin" in q
                is_price  = any(w in q for w in ["above","below","higher","lower","up","down","price"])
                if is_crypto and is_price:
                    token_ids = m.get("clobTokenIds")
                    if token_ids:
                        if isinstance(token_ids, str):
                            try: token_ids = json.loads(token_ids)
                            except: continue
                        btc.append({
                            "id":          m.get("id"),
                            "question":    m.get("question"),
                            "conditionId": m.get("conditionId"),
                            "yes_token":   token_ids[0] if len(token_ids)>0 else None,
                            "no_token":    token_ids[1] if len(token_ids)>1 else None,
                            "end_date":    m.get("endDate"),
                            "volume":      float(m.get("volume") or 0),
                        })

            # Ordena por volume e pega top 10
            btc.sort(key=lambda x: x["volume"], reverse=True)
            self.btc_markets = btc[:10]
            self.stats["markets_tracked"] = len(self.btc_markets)

            for m in self.btc_markets[:3]:
                print(f"  → {m['question'][:60]}...")

        except Exception as e:
            print(f"[PolyScanner] Erro buscar mercados: {e}")

    async def _poll_orderbooks(self):
        """Lê orderbook de cada mercado a cada 500ms"""
        while self.running:
            for market in self.btc_markets:
                for side, token_key in [("YES", "yes_token"), ("NO", "no_token")]:
                    token_id = market.get(token_key)
                    if not token_id:
                        continue
                    try:
                        book = await self._get_orderbook(token_id)
                        if book:
                            key = f"{market['id']}_{side}"
                            prev = self.orderbooks.get(key)
                            self.orderbooks[key] = book

                            # Detecta ordem grande nova
                            if prev:
                                await self._detect_large_order(
                                    market, side, token_id, prev, book
                                )
                    except:
                        pass
            await asyncio.sleep(0.5)

    async def _get_orderbook(self, token_id: str) -> Optional[dict]:
        try:
            async with self._session.get(
                f"{CLOB_API}/book",
                params={"token_id": token_id},
                timeout=aiohttp.ClientTimeout(total=3)
            ) as r:
                if r.status == 200:
                    return await r.json()
        except:
            pass
        return None

    async def _detect_large_order(self, market: dict, side: str,
                                    token_id: str, prev: dict, curr: dict):
        """
        Compara orderbook anterior com atual.
        Se apareceu volume grande novo → ordem grande detectada.
        """
        self.stats["orders_seen"] += 1

        # Calcula volume total nos melhores níveis
        def top_volume(book: dict, n: int = 3) -> float:
            bids = book.get("bids", [])[:n]
            asks = book.get("asks", [])[:n]
            total = 0
            for entry in bids + asks:
                try:
                    price = float(entry.get("price", 0))
                    size  = float(entry.get("size", 0))
                    total += price * size
                except:
                    pass
            return total

        prev_vol = top_volume(prev)
        curr_vol = top_volume(curr)
        delta    = curr_vol - prev_vol

        if delta < MIN_ORDER_SIZE_USD:
            return

        # Determina direção da ordem
        curr_bids = curr.get("bids", [])
        curr_asks = curr.get("asks", [])

        best_bid = float(curr_bids[0]["price"]) if curr_bids else 0
        best_ask = float(curr_asks[0]["price"]) if curr_asks else 1

        mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0.5

        # Ordem grande de compra → preço vai subir
        order = {
            "market_id":   market["id"],
            "question":    market["question"],
            "side":        side,
            "token_id":    token_id,
            "delta_usd":   round(delta, 2),
            "mid_price":   round(mid_price, 4),
            "best_bid":    round(best_bid, 4),
            "best_ask":    round(best_ask, 4),
            "spread":      round(best_ask - best_bid, 4),
            "timestamp":   time.time(),
            "direction":   "BUY" if delta > 0 else "SELL",
        }

        self.large_orders.insert(0, order)
        self.large_orders = self.large_orders[:100]
        self.stats["large_orders"] += 1

        print(f"[PolyScanner] 🔥 Ordem grande: {side} {market['question'][:40]}... "
              f"${delta:.0f} @ {mid_price:.3f}")

        if self.on_large_order:
            await self.on_large_order(order)

    async def _refresh_markets_loop(self):
        """Atualiza lista de mercados a cada 5 minutos"""
        while self.running:
            await asyncio.sleep(300)
            await self._find_btc_markets()

    def get_orderbook(self, market_id: str, side: str) -> Optional[dict]:
        return self.orderbooks.get(f"{market_id}_{side}")
