"""
Gerador de dados históricos realistas para backtest Polymarket BTC 5min
Simula: preço BTC, odds do mercado, e resultado (UP/DOWN)
Baseado em comportamento real do BTC — volatilidade, tendências, reversões
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generate_btc_history(days: int = 30, seed: int = 42) -> pd.DataFrame:
    """
    Gera histórico realista de BTC com candles de 1 minuto
    e mercados Polymarket de 5 minutos correspondentes
    """
    np.random.seed(seed)
    n_minutes = days * 24 * 60
    
    # Parâmetros realistas do BTC
    base_price = 65000
    volatility = 0.0008      # 0.08% por minuto (~1.7% por hora)
    drift = 0.00002          # leve viés positivo
    
    # Gera preços com GBM (Geometric Brownian Motion)
    returns = np.random.normal(drift, volatility, n_minutes)
    # Adiciona saltos ocasionais (news, liquidações)
    jumps = np.random.choice([0, 1], size=n_minutes, p=[0.99, 0.01])
    jump_sizes = np.random.normal(0, 0.005, n_minutes) * jumps
    returns += jump_sizes
    
    prices = base_price * np.exp(np.cumsum(returns))
    
    timestamps = [datetime(2025, 1, 1) + timedelta(minutes=i) for i in range(n_minutes)]
    
    df_1min = pd.DataFrame({
        "timestamp": timestamps,
        "price": prices,
        "volume": np.random.uniform(100, 2000, n_minutes) * (1 + np.abs(returns) * 100)
    })
    
    # Agrega em janelas de 5 minutos (mercados Polymarket)
    records = []
    for i in range(0, n_minutes - 5, 5):
        window = df_1min.iloc[i:i+5]
        open_price  = window.iloc[0]["price"]
        close_price = window.iloc[-1]["price"]
        high_price  = window["price"].max()
        low_price   = window["price"].min()
        move_pct    = (close_price - open_price) / open_price * 100
        
        # Simula odds do Polymarket
        # Odds refletem o movimento ANTERIOR + momentum
        prev_move = 0
        if i >= 5:
            prev_window = df_1min.iloc[i-5:i]
            prev_move = (prev_window.iloc[-1]["price"] - prev_window.iloc[0]["price"]) / prev_window.iloc[0]["price"] * 100
        
        # Market maker ajusta odds baseado em momentum
        base_odds = 0.50
        momentum_adj = np.clip(prev_move * 3, -0.15, 0.15)
        noise = np.random.normal(0, 0.03)
        
        yes_odds_open = np.clip(base_odds + momentum_adj + noise, 0.20, 0.80)
        
        # Odds no momento T-30s (quando nosso bot entra com delay)
        # Mercado já ajustou parcialmente baseado no movimento atual
        early_move = (df_1min.iloc[i+1]["price"] - open_price) / open_price * 100
        delay_adj  = np.clip(early_move * 5, -0.10, 0.10)
        yes_odds_delayed = np.clip(yes_odds_open + delay_adj + np.random.normal(0, 0.01), 0.25, 0.75)
        
        # Resultado real
        outcome_up = close_price > open_price
        
        # Indicadores técnicos dos últimos 15min
        lookback = df_1min.iloc[max(0,i-15):i]
        if len(lookback) >= 5:
            rsi_proxy = 50 + (prev_move * 10)  # simplificado
            vol_ratio = window["volume"].mean() / (lookback["volume"].mean() + 1e-10)
        else:
            rsi_proxy = 50
            vol_ratio = 1.0
        
        records.append({
            "timestamp":        window.iloc[0]["timestamp"],
            "open":             open_price,
            "close":            close_price,
            "high":             high_price,
            "low":              low_price,
            "move_pct":         move_pct,
            "prev_move_pct":    prev_move,
            "yes_odds_open":    round(yes_odds_open, 4),
            "yes_odds_delayed": round(yes_odds_delayed, 4),
            "outcome_up":       outcome_up,
            "volume":           window["volume"].sum(),
            "rsi_proxy":        rsi_proxy,
            "vol_ratio":        vol_ratio,
        })
    
    return pd.DataFrame(records)


if __name__ == "__main__":
    df = generate_btc_history(30)
    print(f"✓ {len(df)} janelas de 5min geradas")
    print(f"  Período: {df['timestamp'].min()} → {df['timestamp'].max()}")
    print(f"  Preço inicial: ${df['open'].iloc[0]:,.0f}")
    print(f"  Preço final:   ${df['close'].iloc[-1]:,.0f}")
    print(f"  UP wins: {df['outcome_up'].mean()*100:.1f}%")
    print(f"\nAmostra:")
    print(df[['timestamp','open','close','move_pct','yes_odds_open','yes_odds_delayed','outcome_up']].head(5).to_string())
