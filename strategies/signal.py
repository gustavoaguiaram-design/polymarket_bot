"""
Estratégia de sinal para Polymarket BTC 5min
Combina: Window Delta, Momentum, RSI, Volume
Retorna direção e confiança ANTES de entrar no mercado
"""
import numpy as np
import pandas as pd
from typing import Optional


def calculate_signal(row: pd.Series, history: pd.DataFrame) -> dict:
    """
    Analisa janela atual e decide se entra e em qual direção.
    
    row      = dados da janela atual (open, prev_move_pct, rsi_proxy, vol_ratio)
    history  = últimas N janelas para contexto
    
    Retorna:
        signal:     'UP' | 'DOWN' | 'NEUTRAL'
        confidence: 0.0 - 1.0
        edge:       vantagem estimada sobre as odds
        reason:     explicação
    """
    score = 0.0
    reasons = []

    prev_move = row["prev_move_pct"]
    rsi       = row["rsi_proxy"]
    vol_ratio = row["vol_ratio"]

    # ── 1. Momentum das últimas 3 janelas ─────────────────────────────────────
    if len(history) >= 3:
        last3 = history["move_pct"].tail(3).values
        momentum = np.mean(last3)
        consistency = np.sign(last3).sum() / 3  # -1 a +1

        if abs(momentum) > 0.05 and abs(consistency) >= 0.67:
            score += np.sign(momentum) * 2.5
            reasons.append(f"Momentum {momentum:+.3f}% consistente")
    else:
        momentum = 0

    # ── 2. Reversão (Tradeiros style) ─────────────────────────────────────────
    if len(history) >= 5:
        last5_move = history["move_pct"].tail(5).sum()
        if abs(last5_move) > 0.3:
            # Movimento grande → reversão provável
            score -= np.sign(last5_move) * 2.0
            reasons.append(f"Reversão após {last5_move:+.2f}% acumulado")

    # ── 3. RSI extremo ─────────────────────────────────────────────────────────
    if rsi > 70:
        score -= 1.5
        reasons.append(f"RSI alto ({rsi:.0f}) → DOWN")
    elif rsi < 30:
        score += 1.5
        reasons.append(f"RSI baixo ({rsi:.0f}) → UP")

    # ── 4. Volume confirma ─────────────────────────────────────────────────────
    if vol_ratio > 1.5 and abs(prev_move) > 0.05:
        score += np.sign(prev_move) * 1.0
        reasons.append(f"Volume {vol_ratio:.1f}x confirma direção")

    # ── 5. Movimento anterior (Window Delta) ───────────────────────────────────
    if abs(prev_move) > 0.10:
        score += np.sign(prev_move) * 1.5
        reasons.append(f"Window Delta {prev_move:+.3f}%")

    # ── Normaliza e converte ───────────────────────────────────────────────────
    max_score = 2.5 + 2.0 + 1.5 + 1.0 + 1.5  # = 8.5
    normalized = np.clip(score / max_score, -1, 1)
    confidence = min(abs(score) / 4.0, 1.0)

    if normalized > 0.20:
        signal = "UP"
    elif normalized < -0.20:
        signal = "DOWN"
    else:
        signal = "NEUTRAL"

    return {
        "signal":     signal,
        "confidence": round(confidence, 3),
        "score":      round(normalized, 3),
        "reasons":    reasons
    }


def calculate_edge(signal: str, odds: float) -> float:
    """
    Calcula vantagem matemática sobre as odds do mercado.
    edge > 0 = trade favorável
    edge > 0.05 = trade recomendado
    """
    if signal == "NEUTRAL":
        return 0.0

    # Nossa estimativa de probabilidade real
    # Baseada no sinal — conservadoramente 55-65%
    if signal == "UP":
        our_prob = 0.55 + (1 - odds) * 0.10  # se mercado é pessimista, nossa edge é maior
    else:
        our_prob = 0.55 + odds * 0.10

    # Retorno esperado: prob * (1/odds - 1) - (1-prob) * 1
    if signal == "UP":
        payout = 1.0 / odds - 1  # se odds=0.60, ganho = 1/0.60 - 1 = 0.667
        ev = our_prob * payout - (1 - our_prob) * 1
    else:
        no_odds = 1 - odds
        payout = 1.0 / no_odds - 1
        ev = our_prob * payout - (1 - our_prob) * 1

    return round(ev, 4)
