#!/usr/bin/env python3
"""
Polymarket Flow Bot — Ponto de entrada
"""
import uvicorn
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════╗
║         POLYMARKET FLOW BOT v1.0                     ║
║   Leitura de Fluxo de Ordens + Confirmação BTC       ║
╚══════════════════════════════════════════════════════╝

→ Dashboard: http://localhost:8001
→ API:        http://localhost:8001/api/status
→ Modo:       PAPER TRADING (seguro para testar)
""")
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=False, log_level="warning")
