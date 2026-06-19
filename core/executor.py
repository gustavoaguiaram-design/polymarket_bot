"""
Executor Polymarket — paper trading e real
Paper: simula execução com preços reais do orderbook
Real: executa via py-clob-client
"""
import asyncio
import aiohttp
import time
from typing import Optional, Dict
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (
    CLOB_API, BET_SIZE_USD, MAX_POSITIONS,
    PAPER_TRADING, PAPER_BALANCE,
    POLY_PRIVATE_KEY, POLY_FUNDER
)


class PolyExecutor:
    def __init__(self):
        self.paper          = PAPER_TRADING
        self.paper_balance  = PAPER_BALANCE
        self.positions: Dict[str, dict] = {}
        self.closed_trades: list = []
        self.daily_pnl      = 0.0
        self._session: Optional[aiohttp.ClientSession] = None
        self.stats = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
        }

    async def start(self):
        self._session = aiohttp.ClientSession()
        mode = "PAPER" if self.paper else "REAL"
        print(f"[PolyExec] Modo: {mode} | Saldo: ${self.paper_balance:.2f}")

    async def stop(self):
        if self._session:
            await self._session.close()

    async def open_position(self, signal: dict) -> Optional[dict]:
        """Abre posição baseada no sinal de fluxo"""
        if len(self.positions) >= MAX_POSITIONS:
            return None

        key = f"{signal['market_id']}_{signal['side']}"
        if key in self.positions:
            return None

        if self.paper_balance < BET_SIZE_USD:
            return None

        trade = {
            "id":          key,
            "market_id":   signal["market_id"],
            "question":    signal["question"][:60],
            "direction":   signal["direction"],
            "side":        signal["side"],
            "token_id":    signal["token_id"],
            "entry_price": signal["entry_price"],
            "tp_price":    signal["tp_price"],
            "sl_price":    signal["sl_price"],
            "edge":        signal["edge"],
            "bet":         BET_SIZE_USD,
            "opened_at":   time.time(),
            "paper":       self.paper,
            "pnl":         0.0,
        }

        if self.paper:
            self.paper_balance -= BET_SIZE_USD
            self.positions[key] = trade
            print(f"[Paper] ✓ {signal['direction']} @ {signal['entry_price']:.3f} "
                  f"| TP:{signal['tp_price']:.3f} SL:{signal['sl_price']:.3f} "
                  f"| Edge:{signal['edge']:.1%}")
            return trade

        # Real — precisa de py-clob-client instalado e wallet configurada
        return await self._execute_real(trade, signal)

    async def _execute_real(self, trade: dict, signal: dict) -> Optional[dict]:
        """Executa ordem real no Polymarket via CLOB API"""
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import MarketOrderArgs, OrderType
            from py_clob_client.order_builder.constants import BUY

            client = ClobClient(
                CLOB_API,
                key=POLY_PRIVATE_KEY,
                chain_id=137,
                signature_type=1,
                funder=POLY_FUNDER
            )
            client.set_api_creds(client.create_or_derive_api_creds())

            # Tamanho em USDC
            amount = BET_SIZE_USD

            order = MarketOrderArgs(
                token_id=signal["token_id"],
                amount=amount,
                side=BUY,
                order_type=OrderType.FOK  # Fill or Kill — executa agora ou cancela
            )
            signed = client.create_market_order(order)
            resp   = client.post_order(signed, OrderType.FOK)

            if resp.get("success"):
                print(f"[REAL] ✓ Ordem executada: {resp}")
                self.positions[trade["id"]] = trade
                return trade
            else:
                print(f"[REAL] ✗ Falha: {resp}")
                return None

        except ImportError:
            print("[PolyExec] py-clob-client não instalado. Rodando em paper.")
            self.paper = True
            return await self.open_position(signal)
        except Exception as e:
            print(f"[PolyExec] Erro real: {e}")
            return None

    async def update_positions(self, scanner) -> list:
        """Monitora posições abertas e fecha quando TP/SL é atingido"""
        closed = []

        for key, pos in list(self.positions.items()):
            # Busca preço atual do orderbook
            book = scanner.get_orderbook(pos["market_id"], pos["side"])
            if not book:
                continue

            bids = book.get("bids", [])
            asks = book.get("asks", [])
            if not bids and not asks:
                continue

            try:
                best_bid = float(bids[0]["price"]) if bids else 0
                best_ask = float(asks[0]["price"]) if asks else 1
                mid = (best_bid + best_ask) / 2
            except:
                continue

            entry = pos["entry_price"]
            pnl_pct = (mid - entry) / entry

            # Calcula PnL
            pnl = pos["bet"] * pnl_pct
            pos["pnl"] = round(pnl, 4)
            pos["current_price"] = round(mid, 4)

            # Verifica TP/SL
            hit_tp = mid >= pos["tp_price"]
            hit_sl = mid <= pos["sl_price"]

            # Timeout: fecha após 10 minutos se não atingiu TP/SL
            elapsed = time.time() - pos["opened_at"]
            timeout = elapsed > 600

            if hit_tp or hit_sl or timeout:
                exit_price = mid
                final_pnl  = pos["bet"] * (exit_price - entry) / entry

                if self.paper:
                    self.paper_balance += pos["bet"] + final_pnl

                self.daily_pnl         += final_pnl
                self.stats["total_pnl"] += final_pnl
                self.stats["total_trades"] += 1

                reason = "TP" if hit_tp else "SL" if hit_sl else "TIMEOUT"
                won = final_pnl > 0

                if won: self.stats["wins"] += 1
                else:   self.stats["losses"] += 1

                pos.update({
                    "exit_price":  round(exit_price, 4),
                    "final_pnl":   round(final_pnl, 4),
                    "close_reason": reason,
                    "won":         won,
                })

                emoji = "✓" if won else "✗"
                print(f"[Paper] {emoji} {reason} {pos['question'][:30]} "
                      f"@ {exit_price:.3f} | PnL: ${final_pnl:+.4f}")

                self.closed_trades.insert(0, pos.copy())
                self.closed_trades = self.closed_trades[:200]
                closed.append(pos.copy())
                del self.positions[key]

        return closed

    def get_portfolio(self) -> dict:
        wins   = self.stats["wins"]
        total  = self.stats["total_trades"]
        return {
            "balance":        round(self.paper_balance, 2),
            "open_positions": len(self.positions),
            "daily_pnl":      round(self.daily_pnl, 2),
            "total_pnl":      round(self.stats["total_pnl"], 2),
            "total_trades":   total,
            "win_rate":       round(wins/total*100, 1) if total > 0 else 0,
            "paper":          self.paper,
        }

    def get_open_positions(self) -> list:
        return list(self.positions.values())
