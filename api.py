"""
API + Dashboard do Polymarket Flow Bot
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import asyncio
import json
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from engine import engine, state
from config import API_PORT

app = FastAPI(title="Polymarket Flow Bot")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ws_clients = []


@app.on_event("startup")
async def startup():
    asyncio.create_task(engine.start())
    asyncio.create_task(_broadcaster())


@app.on_event("shutdown")
async def shutdown():
    await engine.stop()


@app.get("/api/status")
async def status():
    return {
        **state,
        "portfolio":    engine.executor.get_portfolio(),
        "scanner_stats": engine.scanner.stats,
    }


@app.get("/api/positions")
async def positions():
    return engine.executor.get_open_positions()


@app.get("/api/trades")
async def trades():
    return engine.executor.closed_trades[:50]


@app.get("/api/flow-log")
async def flow_log():
    return state["flow_log"]


@app.get("/api/markets")
async def markets():
    return engine.scanner.btc_markets


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)


async def _broadcaster():
    while True:
        if ws_clients:
            data = {
                "type":      "update",
                "timestamp": datetime.utcnow().isoformat(),
                "portfolio": engine.executor.get_portfolio(),
                "positions": engine.executor.get_open_positions(),
                "flow_log":  state["flow_log"][:5],
                "stats":     engine.scanner.stats,
            }
            dead = []
            for ws in ws_clients:
                try:
                    await ws.send_text(json.dumps(data))
                except:
                    dead.append(ws)
            for ws in dead:
                if ws in ws_clients:
                    ws_clients.remove(ws)
        await asyncio.sleep(1)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<title>Polymarket Flow Bot</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
  :root{--bg:#06090f;--bg2:#0c1219;--bg3:#111a24;--border:#1a2535;
    --text:#e2e8f0;--text2:#7a8fa6;--text3:#4a6080;
    --green:#00d68f;--red:#ff4757;--blue:#3d9fff;--purple:#a855f7;--yellow:#ffd32a;
    --mono:'JetBrains Mono',monospace;--sans:'Inter',sans-serif;}
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh;}
  header{display:flex;align-items:center;justify-content:space-between;
    padding:14px 24px;background:var(--bg2);border-bottom:1px solid var(--border);
    position:sticky;top:0;z-index:100;}
  .logo{font-size:17px;font-weight:700;display:flex;align-items:center;gap:10px;}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--green);
    box-shadow:0 0 8px var(--green);animation:pulse 2s infinite;}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
  .hstats{display:flex;gap:24px;}
  .hs{text-align:right;}
  .hs-label{font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:1px;}
  .hs-val{font-size:15px;font-weight:600;font-family:var(--mono);}
  .badge{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;
    text-transform:uppercase;letter-spacing:.5px;}
  .badge-paper{background:rgba(255,211,42,.15);color:var(--yellow);}
  .badge-live{background:rgba(0,214,143,.15);color:var(--green);}
  .layout{display:grid;grid-template-columns:1fr 360px;gap:0;height:calc(100vh - 53px);}
  .main{overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px;}
  .sidebar{background:var(--bg2);border-left:1px solid var(--border);overflow-y:auto;}
  .card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:16px;}
  .card-title{font-size:12px;font-weight:600;color:var(--text2);
    text-transform:uppercase;letter-spacing:.8px;margin-bottom:14px;}
  .stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;}
  .stat{background:var(--bg2);border:1px solid var(--border);border-radius:10px;
    padding:16px;position:relative;overflow:hidden;}
  .stat::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;}
  .stat.g::before{background:var(--green);}
  .stat.b::before{background:var(--blue);}
  .stat.p::before{background:var(--purple);}
  .stat.r::before{background:var(--red);}
  .stat-label{font-size:11px;color:var(--text3);text-transform:uppercase;
    letter-spacing:.8px;margin-bottom:8px;}
  .stat-val{font-size:22px;font-weight:700;font-family:var(--mono);line-height:1;}
  .stat-sub{font-size:11px;color:var(--text2);margin-top:4px;}
  .flow-item{padding:12px 16px;border-bottom:1px solid var(--border);}
  .flow-header{display:flex;justify-content:space-between;margin-bottom:6px;}
  .flow-q{font-size:12px;color:var(--text2);}
  .flow-time{font-size:10px;color:var(--text3);}
  .flow-body{display:flex;gap:8px;align-items:center;}
  .tag{padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;font-family:var(--mono);}
  .tag-buy{background:rgba(0,214,143,.15);color:var(--green);}
  .tag-sell{background:rgba(255,71,87,.15);color:var(--red);}
  .tag-edge{background:rgba(61,159,255,.12);color:var(--blue);}
  .pos-item{display:grid;grid-template-columns:1fr auto auto;gap:12px;
    align-items:center;padding:12px 0;border-bottom:1px solid var(--border);}
  .pos-q{font-size:12px;color:var(--text2);}
  .pos-dir{font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;}
  .pos-pnl{font-family:var(--mono);font-size:13px;font-weight:600;}
  .empty{padding:40px;text-align:center;color:var(--text3);font-size:13px;}
  .scanning{animation:scan 2s ease-in-out infinite;}
  @keyframes scan{0%,100%{opacity:1}50%{opacity:.4}}
  .market-item{padding:10px 16px;border-bottom:1px solid var(--border);font-size:12px;}
  .market-q{color:var(--text2);margin-bottom:4px;}
  .market-vol{color:var(--text3);font-family:var(--mono);font-size:11px;}
  ::-webkit-scrollbar{width:4px;}
  ::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px;}
  .positive{color:var(--green);}
  .negative{color:var(--red);}
</style>
</head>
<body>
<header>
  <div class="logo"><div class="dot"></div>POLY FLOW BOT</div>
  <div class="hstats">
    <div class="hs"><div class="hs-label">Saldo</div><div class="hs-val positive" id="hBal">$—</div></div>
    <div class="hs"><div class="hs-label">PnL Hoje</div><div class="hs-val" id="hPnl">$—</div></div>
    <div class="hs"><div class="hs-label">Ordens Vistas</div><div class="hs-val" id="hOrders">—</div></div>
    <div class="hs"><div class="hs-label">Trades</div><div class="hs-val" id="hTrades">—</div></div>
  </div>
  <span class="badge badge-paper" id="modeBadge">PAPER</span>
</header>

<div class="layout">
  <div class="main">
    <div class="stats-grid">
      <div class="stat g">
        <div class="stat-label">Saldo</div>
        <div class="stat-val positive" id="balance">$500</div>
        <div class="stat-sub" id="openPos">0 posições abertas</div>
      </div>
      <div class="stat b">
        <div class="stat-label">PnL Total</div>
        <div class="stat-val" id="totalPnl">$0.00</div>
        <div class="stat-sub" id="winRate">Win Rate: —</div>
      </div>
      <div class="stat p">
        <div class="stat-label">Ordens Detectadas</div>
        <div class="stat-val" id="ordersDetected">0</div>
        <div class="stat-sub" id="signalsTaken">Executadas: 0</div>
      </div>
      <div class="stat r">
        <div class="stat-label">Mercados Rastreados</div>
        <div class="stat-val" id="marketsTracked">0</div>
        <div class="stat-sub">BTC/Crypto ativos</div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Posições Abertas</div>
      <div id="positions"><div class="empty">Nenhuma posição aberta</div></div>
    </div>

    <div class="card">
      <div class="card-title">Últimos Trades</div>
      <div id="trades"><div class="empty scanning">Aguardando primeiro trade...</div></div>
    </div>

    <div class="card">
      <div class="card-title">Mercados Monitorados</div>
      <div id="markets"><div class="empty scanning">Carregando mercados...</div></div>
    </div>
  </div>

  <div class="sidebar">
    <div style="padding:14px 16px 10px;font-size:11px;font-weight:600;color:var(--text3);
      text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid var(--border);">
      Flow Log — Ordens Grandes
    </div>
    <div id="flowLog"><div class="empty scanning">Escaneando orderbook...</div></div>
  </div>
</div>

<script>
const API = window.location.origin;

function connectWS(){
  const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(wsProto + '//' + window.location.host + '/ws');
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if(d.type==='update'){
      updatePortfolio(d.portfolio);
      updatePositions(d.positions);
      if(d.flow_log) updateFlowLog(d.flow_log);
      if(d.stats) updateStats(d.stats);
    }
  };
  ws.onclose = () => setTimeout(connectWS, 2000);
}

function updatePortfolio(p){
  if(!p) return;
  document.getElementById('hBal').textContent = '$'+p.balance.toFixed(2);
  document.getElementById('balance').textContent = '$'+p.balance.toFixed(2);
  document.getElementById('openPos').textContent = p.open_positions+' posições abertas';
  const pnl = p.daily_pnl||0;
  const pnlEl = document.getElementById('hPnl');
  pnlEl.textContent = (pnl>=0?'+':'')+'$'+pnl.toFixed(2);
  pnlEl.className = 'hs-val '+(pnl>=0?'positive':'negative');
  document.getElementById('totalPnl').textContent = '$'+p.total_pnl.toFixed(2);
  document.getElementById('totalPnl').className = 'stat-val '+(p.total_pnl>=0?'positive':'negative');
  document.getElementById('winRate').textContent = 'Win Rate: '+p.win_rate+'%';
  document.getElementById('hTrades').textContent = p.total_trades;
}

function updateStats(s){
  document.getElementById('ordersDetected').textContent = s.orders_seen||0;
  document.getElementById('marketsTracked').textContent = s.markets_tracked||0;
}

function updatePositions(positions){
  const el = document.getElementById('positions');
  if(!positions||positions.length===0){
    el.innerHTML='<div class="empty">Nenhuma posição aberta</div>'; return;
  }
  el.innerHTML = positions.map(p=>{
    const pnl = p.pnl||0;
    const dc = p.direction.includes('YES')?'tag-buy':'tag-sell';
    return `<div class="pos-item">
      <div><div style="font-size:13px;font-weight:600;font-family:var(--mono)">${p.direction}</div>
        <div class="pos-q">${p.question}</div></div>
      <div class="pos-dir ${dc}">${p.side}</div>
      <div class="pos-pnl ${pnl>=0?'positive':'negative'}">${pnl>=0?'+':''}$${pnl.toFixed(4)}</div>
    </div>`;
  }).join('');
}

function updateFlowLog(log){
  const el = document.getElementById('flowLog');
  if(!log||log.length===0){
    el.innerHTML='<div class="empty scanning">Escaneando orderbook...</div>'; return;
  }
  el.innerHTML = log.map(l=>{
    const t = new Date(l.timestamp).toLocaleTimeString('pt-BR');
    const dc = l.direction.includes('YES')?'tag-buy':'tag-sell';
    return `<div class="flow-item">
      <div class="flow-header">
        <div class="flow-q">${l.question}</div>
        <div class="flow-time">${t}</div>
      </div>
      <div class="flow-body">
        <span class="tag ${dc}">${l.direction}</span>
        <span class="tag tag-edge">Edge ${(l.edge*100).toFixed(1)}%</span>
        <span style="font-size:11px;color:var(--text3)">$${l.delta_usd.toFixed(0)}</span>
      </div>
    </div>`;
  }).join('');
}

async function loadMarkets(){
  try{
    const r = await fetch(API+'/api/markets');
    const ms = await r.json();
    const el = document.getElementById('markets');
    if(!ms||ms.length===0){
      el.innerHTML='<div class="empty">Nenhum mercado BTC encontrado</div>'; return;
    }
    el.innerHTML = ms.map(m=>`
      <div class="market-item">
        <div class="market-q">${m.question}</div>
        <div class="market-vol">Volume: $${parseFloat(m.volume||0).toLocaleString()}</div>
      </div>`).join('');
  }catch(e){}
}

async function loadTrades(){
  try{
    const r = await fetch(API+'/api/trades');
    const ts = await r.json();
    const el = document.getElementById('trades');
    if(!ts||ts.length===0){
      el.innerHTML='<div class="empty scanning">Aguardando primeiro trade...</div>'; return;
    }
    el.innerHTML = ts.slice(0,10).map(t=>{
      const pnl = t.final_pnl||0;
      return `<div class="pos-item">
        <div><div style="font-size:12px;font-weight:600">${t.close_reason}</div>
          <div class="pos-q">${t.question}</div></div>
        <span class="tag ${t.won?'tag-buy':'tag-sell'}">${t.won?'WIN':'LOSS'}</span>
        <div class="pos-pnl ${pnl>=0?'positive':'negative'}">${pnl>=0?'+':''}$${pnl.toFixed(4)}</div>
      </div>`;
    }).join('');
  }catch(e){}
}

async function loadStatus(){
  try{
    const r = await fetch(API+'/api/status');
    const d = await r.json();
    document.getElementById('hOrders').textContent = d.signals_seen||0;
    document.getElementById('signalsTaken').textContent = 'Executadas: '+(d.signals_taken||0);
    document.getElementById('modeBadge').textContent = d.portfolio?.paper ? 'PAPER' : 'LIVE';
    updatePortfolio(d.portfolio);
    if(d.scanner_stats) updateStats(d.scanner_stats);
  }catch(e){}
}

loadStatus();
loadMarkets();
loadTrades();
connectWS();

setInterval(loadMarkets, 30000);
setInterval(loadTrades, 10000);
setInterval(loadStatus, 5000);
</script>
</body>
</html>"""
