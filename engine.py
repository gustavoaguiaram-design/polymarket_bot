"""
Motor principal do Polymarket Flow Bot
"""
import asyncio
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from core.scanner import OrderFlowScanner
from core.executor import PolyExecutor
from strategies.flow import FlowStrategy

state = {
    "running": False,
    "started_at": None,
    "signals_seen": 0,
    "signals_taken": 0,
    "flow_log": [],
}


class PolyEngine:
    def __init__(self):
        self.scanner  = OrderFlowScanner()
        self.executor = PolyExecutor()
        self.strategy = FlowStrategy()

    async def start(self):
        await self.executor.start()
        await self.strategy.start()
        await self.scanner.start(on_large_order=self._on_large_order)

        state["running"]    = True
        state["started_at"] = datetime.utcnow().isoformat()

        print(f"[PolyEngine] Bot iniciado | Paper: {self.executor.paper}")
        asyncio.create_task(self._monitor_loop())

    async def stop(self):
        state["running"] = False
        await self.scanner.stop()
        await self.strategy.stop()
        await self.executor.stop()

    async def _on_large_order(self, order: dict):
        """Callback quando ordem grande é detectada"""
        state["signals_seen"] += 1

        # Analisa se vale entrar
        signal = self.strategy.analyze(order, self.scanner)
        if not signal:
            return

        # Log do fluxo
        state["flow_log"].insert(0, {
            "timestamp":   datetime.utcnow().isoformat(),
            "question":    order["question"][:50],
            "side":        order["side"],
            "delta_usd":   order["delta_usd"],
            "edge":        signal["edge"],
            "btc_mom":     signal["btc_momentum"],
            "direction":   signal["direction"],
        })
        state["flow_log"] = state["flow_log"][:50]

        # Executa
        trade = await self.executor.open_position(signal)
        if trade:
            state["signals_taken"] += 1

    async def _monitor_loop(self):
        """Monitora posições a cada 5 segundos"""
        while state["running"]:
            try:
                await self.executor.update_positions(self.scanner)
            except Exception as e:
                print(f"[PolyEngine] Erro monitor: {e}")
            await asyncio.sleep(5)


engine = PolyEngine()
