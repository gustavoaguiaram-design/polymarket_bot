# RELATÓRIO: Polymarket BTC 5min vs Binance Futures

## Resultados do Backtest (30 dias, 10 cenários)

### Cenário 1: SEM delay (ideal, impossível na prática)
- Win rate médio: 52.1%
- Lucrativo em apenas: 30% dos cenários
- PnL médio: -$25.23 (NEGATIVO)

### Cenário 2: COM delay 30s (realista)
- Win rate médio: 32.9%
- Lucrativo em: 0% dos cenários
- PnL médio: -$999.85 (FALÊNCIA TOTAL)

---

## Conclusão Matemática Final

| | Polymarket (sem delay) | Polymarket (delay 30s) | Binance Futures |
|---|---|---|---|
| Win rate necessário p/ empatar | 50%+ | 62%+ | 30% |
| Win rate real obtido | 52% (marginal) | 33% (inviável) | estimado 55% |
| Lucrativo em X/10 cenários | 3/10 | 0/10 | estimado 7/10 |
| Risco de falência | Alto | Certo | Baixo |

## Veredicto

**Polymarket BTC 5min NÃO é viável** para o setup atual por 3 razões:

1. **Delay é fatal**: 30 segundos de atraso reduz win rate de 52% → 33%,
   abaixo do break-even de 62% exigido pelas odds

2. **Sem edge consistente**: mesmo SEM delay, apenas 30% dos períodos 
   foram lucrativos — a estratégia não tem edge robusto neste timeframe

3. **Binance Futures é melhor**: menor win rate necessário (30% vs 62%),
   alavancagem amplifica ganhos, sem risco de blockchain

## Recomendação

Manter foco no bot da Binance Futures atual.
Polymarket só faria sentido com:
- VPS dedicado < 5ms de latência
- Strategy com win rate > 65% comprovado
- Capital inicial > $500 para diluir gas fees
