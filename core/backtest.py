"""
Motor de backtest Polymarket BTC 5min
Testa 3 cenários: sem delay, com delay 30s, com delay 60s
"""
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.generator import generate_btc_history
from strategies.signal import calculate_signal, calculate_edge


def run_backtest(
    df: pd.DataFrame,
    bet_size: float = 10.0,
    min_confidence: float = 0.55,
    min_edge: float = 0.02,
    delay_scenario: str = "no_delay",  # no_delay | delay_30s | delay_60s
    use_kelly: bool = False,
    max_bet: float = 25.0,
) -> dict:
    """
    Roda backtest completo.
    delay_scenario define qual coluna de odds usar:
        no_delay  → yes_odds_open (entra na abertura)
        delay_30s → yes_odds_delayed (entra 30s depois)
        delay_60s → odds ainda mais ajustadas
    """
    trades = []
    balance = 1000.0  # saldo inicial simulado
    peak = balance

    for i in range(15, len(df)):  # começa com 15 janelas de histórico
        row = df.iloc[i]
        history = df.iloc[max(0, i-15):i]

        # Calcula sinal
        sig = calculate_signal(row, history)

        if sig["signal"] == "NEUTRAL":
            continue
        if sig["confidence"] < min_confidence:
            continue

        # Escolhe odds baseado no cenário de delay
        if delay_scenario == "no_delay":
            odds = row["yes_odds_open"]
        elif delay_scenario == "delay_30s":
            odds = row["yes_odds_delayed"]
        else:
            # delay_60s — odds ainda mais ajustadas (mercado já reagiu mais)
            odds = np.clip(row["yes_odds_delayed"] + np.random.normal(0, 0.02), 0.25, 0.75)

        # Calcula edge
        edge = calculate_edge(sig["signal"], odds)
        if edge < min_edge:
            continue

        # Tamanho da aposta (Kelly opcional)
        if use_kelly:
            # Kelly fraction: f = (p*b - q) / b onde b = payout, p = prob estimada, q = 1-p
            p = 0.55 + sig["confidence"] * 0.10
            b = 1.0 / (odds if sig["signal"] == "UP" else 1 - odds) - 1
            q = 1 - p
            kelly = (p * b - q) / b if b > 0 else 0
            kelly = max(0, min(kelly * 0.5, 0.20))  # half-kelly, max 20%
            actual_bet = min(balance * kelly, max_bet)
        else:
            actual_bet = min(bet_size, balance)

        if actual_bet < 1.0 or balance < 1.0:
            break

        # Resultado
        outcome_up = row["outcome_up"]
        if sig["signal"] == "UP":
            won = outcome_up
            if won:
                profit = actual_bet * (1.0 / odds - 1)
            else:
                profit = -actual_bet
        else:  # DOWN
            won = not outcome_up
            no_odds = 1 - odds
            if won:
                profit = actual_bet * (1.0 / no_odds - 1)
            else:
                profit = -actual_bet

        balance += profit
        peak = max(peak, balance)
        drawdown = (peak - balance) / peak * 100

        trades.append({
            "timestamp":   row["timestamp"],
            "signal":      sig["signal"],
            "confidence":  sig["confidence"],
            "odds":        odds,
            "edge":        edge,
            "bet":         actual_bet,
            "profit":      round(profit, 4),
            "balance":     round(balance, 4),
            "won":         won,
            "drawdown":    round(drawdown, 2),
            "move_pct":    row["move_pct"],
        })

    if not trades:
        return {"error": "Nenhum trade executado"}

    df_trades = pd.DataFrame(trades)
    total      = len(df_trades)
    wins       = df_trades["won"].sum()
    total_pnl  = df_trades["profit"].sum()
    win_rate   = wins / total * 100
    max_dd     = df_trades["drawdown"].max()
    avg_profit = df_trades[df_trades["won"]]["profit"].mean()
    avg_loss   = df_trades[~df_trades["won"]]["profit"].mean()
    profit_factor = abs(avg_profit / avg_loss) if avg_loss != 0 else 0

    return {
        "scenario":       delay_scenario,
        "total_trades":   total,
        "wins":           int(wins),
        "losses":         total - int(wins),
        "win_rate":       round(win_rate, 2),
        "total_pnl":      round(total_pnl, 2),
        "final_balance":  round(balance, 2),
        "roi_pct":        round((balance - 1000) / 1000 * 100, 2),
        "max_drawdown":   round(max_dd, 2),
        "avg_win":        round(avg_profit, 4) if avg_profit else 0,
        "avg_loss":       round(avg_loss, 4) if avg_loss else 0,
        "profit_factor":  round(profit_factor, 2),
        "trades_per_day": round(total / 30, 1),
        "df_trades":      df_trades,
    }
