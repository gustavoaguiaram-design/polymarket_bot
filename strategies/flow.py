"""
Estratégia de fluxo de ordens para Polymarket
Combina: ordem grande detectada + confirmação do preço BTC
"""
import asyncio
import aiohttp
import time
import numpy as np
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import BINANCE_API, MIN_EDGE, MIN_ODDS, MAX_ODDS


class FlowStrategy:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self.btc_prices: list = []
        self.last_btc_update = 0

    async def start(self):
        self._session = aiohttp.ClientSession()
        asyncio.create_task(self._btc_price_loop())

    async def stop(self):
        if self._session:
            await self._session.close()

    async def _btc_price_loop(self):
        """Atualiza preço BTC a cada 5 segundos"""
        while True:
            try:
                async with self._session.get(
                    f"{BINANCE_API}/fapi/v1/klines",
                    params={"symbol": "BTCUSDT", "interval": "1m", "limit": 10},
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as r:
                    data = await r.json()
                    self.btc_prices = [float(c[4]) for c in data]
                    self.last_btc_update = time.time()
            except:
                pass
            await asyncio.sleep(5)

    def get_btc_momentum(self) -> float:
        """Retorna momentum BTC dos últimos 5 candles de 1min"""
        if len(self.btc_prices) < 3:
            return 0.0
        return (self.btc_prices[-1] - self.btc_prices[-3]) / self.btc_prices[-3] * 100

    def analyze(self, order: dict, scanner) -> Optional[dict]:
        """
        Analisa uma ordem grande detectada e decide se entra.

        Retorna dict com decisão ou None se não entrar.
        """
        mid   = order["mid_price"]
        side  = order["side"]       # YES ou NO
        delta = order["delta_usd"]
        spread = order["spread"]
        bid   = order["best_bid"]
        ask   = order["best_ask"]

        # ── Filtros básicos ────────────────────────────────────────────────────

        # Spread muito alto = mercado ilíquido
        if spread > 0.08:
            return None

        # Odds fora da faixa aceitável
        if mid < MIN_ODDS or mid > MAX_ODDS:
            return None

        # Ordem muito pequena
        if delta < 200:
            return None

        # ── Calcula edge baseado no fluxo ─────────────────────────────────────

        # Quando uma ordem grande de COMPRA entra:
        # → mercado vai precificar YES mais alto
        # → nós compramos YES agora antes do ajuste
        # Edge estimado = spread / 2 + momentum da ordem

        order_momentum = min(delta / 10000, 0.05)  # max 5% de edge por ordem

        # Confirmação com BTC (opcional — não bloqueia se BTC indisponível)
        btc_mom = self.get_btc_momentum()
        btc_confirms = False
        btc_edge = 0.0

        if side == "YES":
            if btc_mom > 0.02:
                btc_confirms = True
                btc_edge = min(btc_mom * 0.5, 0.03)
            elif btc_mom == 0.0:
                # BTC indisponível — não penaliza
                btc_confirms = True
                btc_edge = 0.0
            direction = "BUY_YES"
            entry_price = ask
        else:
            if btc_mom < -0.02:
                btc_confirms = True
                btc_edge = min(abs(btc_mom) * 0.5, 0.03)
            elif btc_mom == 0.0:
                btc_confirms = True
                btc_edge = 0.0
            direction = "BUY_NO"
            entry_price = 1 - bid

        # Edge total
        spread_edge = spread * 0.3  # capturamos parte do spread
        total_edge  = order_momentum + spread_edge + btc_edge

        # Afroxa critério se BTC não confirmou — usa só o fluxo de ordens
        effective_min_edge = MIN_EDGE if btc_confirms else MIN_EDGE * 0.5

        if total_edge < effective_min_edge:
            return None

        # Take profit: quando mercado ajustar o preço
        tp_price = entry_price + (spread * 0.6)
        sl_price = entry_price - (spread * 0.4)

        return {
            "direction":     direction,
            "entry_price":   round(entry_price, 4),
            "tp_price":      round(tp_price, 4),
            "sl_price":      round(sl_price, 4),
            "edge":          round(total_edge, 4),
            "order_size":    delta,
            "btc_confirms":  btc_confirms,
            "btc_momentum":  round(btc_mom, 4),
            "spread":        round(spread, 4),
            "market_id":     order["market_id"],
            "question":      order["question"],
            "token_id":      order["token_id"],
            "side":          side,
        }
