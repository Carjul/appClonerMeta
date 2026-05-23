"""
FB Metrics Dashboard - Meta Ads Performance
Shows Today / Yesterday / Lifetime metrics with dark/light mode.

If tokens are configured, fetches live data from Meta API.
Otherwise uses cached data from last fetch.

Usage:
  pip install flask requests
  python fb_dashboard.py
"""

import json, os, requests, concurrent.futures
from datetime import datetime
from flask import Flask, render_template_string, jsonify

# ============================================================
# CONFIG - Paste your real Meta tokens here for live data
# ============================================================
BM1_TOKEN = "YOUR_BM1_TOKEN_HERE"
BM2_TOKEN = "YOUR_BM2_TOKEN_HERE"

API_VERSION = "v21.0"
BASE = f"https://graph.facebook.com/{API_VERSION}/"

ACCOUNTS = [
    {"name":"MARTHA 2","id":"act_528756616577904","bm":"BM1"},
    {"name":"MARTHA 4","id":"act_708152401990591","bm":"BM1"},
    {"name":"GM-177","id":"act_1027335185283047","bm":"BM1"},
    {"name":"RPG 15","id":"act_2121935234933980","bm":"BM1"},
    {"name":"THM-60","id":"act_1247132143392586","bm":"BM1"},
    {"name":"THM-32","id":"act_1985532452249785","bm":"BM1"},
    {"name":"THM-54","id":"act_1594785768155717","bm":"BM1"},
    {"name":"THM-72","id":"act_1540233950717702","bm":"BM1"},
    {"name":"THM-113","id":"act_1074066461137769","bm":"BM1"},
    {"name":"THM-200","id":"act_1059904599553927","bm":"BM1"},
    {"name":"DG-03","id":"act_1306256300004871","bm":"BM2"},
    {"name":"DG-51","id":"act_900364275348331","bm":"BM2"},
    {"name":"MSTC-20","id":"act_1239484177480232","bm":"BM2"},
    {"name":"THM-119","id":"act_1650693448960867","bm":"BM2"},
    {"name":"KM-19","id":"act_2049541032515377","bm":"BM2"},
    {"name":"THM-55","id":"act_1654285161902955","bm":"BM2"},
]

LIVE_MODE = BM1_TOKEN != "YOUR_BM1_TOKEN_HERE"

# ============================================================
# CACHED DATA (fetched Apr 30 2026 via Craft Agent)
# ============================================================
CACHED = {
    "today": [
        {"name":"THM-119","bm":"BM2","spend":689.61,"purchases":7,"revenue":595.00},
        {"name":"RPG 15","bm":"BM1","spend":60.18,"purchases":0,"revenue":0},
        {"name":"THM-55","bm":"BM2","spend":39.55,"purchases":0,"revenue":0},
        {"name":"THM-72","bm":"BM1","spend":35.77,"purchases":1,"revenue":85.04},
        {"name":"THM-113","bm":"BM1","spend":14.80,"purchases":0,"revenue":0},
        {"name":"THM-200","bm":"BM1","spend":12.07,"purchases":0,"revenue":0},
        {"name":"THM-32","bm":"BM1","spend":1.31,"purchases":0,"revenue":0},
    ],
    "yesterday": [
        {"name":"THM-119","bm":"BM2","spend":1088.93,"purchases":2,"revenue":170.00},
        {"name":"RPG 15","bm":"BM1","spend":140.97,"purchases":2,"revenue":170.03},
        {"name":"THM-55","bm":"BM2","spend":128.14,"purchases":2,"revenue":170.00},
        {"name":"THM-72","bm":"BM1","spend":91.54,"purchases":1,"revenue":85.00},
        {"name":"THM-113","bm":"BM1","spend":52.69,"purchases":0,"revenue":0},
        {"name":"THM-200","bm":"BM1","spend":20.81,"purchases":0,"revenue":0},
    ],
    "lifetime": [
        {"name":"DG-51","bm":"BM2","spend":293445.68,"purchases":2188,"revenue":181610.00},
        {"name":"MSTC-20","bm":"BM2","spend":162889.64,"purchases":2374,"revenue":175712.00},
        {"name":"THM-113","bm":"BM1","spend":90191.78,"purchases":1236,"revenue":90668.00},
        {"name":"GM-177","bm":"BM1","spend":76011.12,"purchases":1403,"revenue":101698.00},
        {"name":"RPG 15","bm":"BM1","spend":39076.67,"purchases":629,"revenue":46477.00},
        {"name":"DG-03","bm":"BM2","spend":38772.64,"purchases":2,"revenue":145.00},
        {"name":"THM-200","bm":"BM1","spend":18860.69,"purchases":159,"revenue":10742.00},
        {"name":"THM-32","bm":"BM1","spend":10631.33,"purchases":68,"revenue":5267.00},
        {"name":"THM-54","bm":"BM1","spend":8303.63,"purchases":94,"revenue":7161.00},
        {"name":"THM-55","bm":"BM2","spend":8148.16,"purchases":85,"revenue":7226.00},
        {"name":"THM-72","bm":"BM1","spend":7345.95,"purchases":78,"revenue":6459.00},
        {"name":"THM-60","bm":"BM1","spend":4044.53,"purchases":33,"revenue":2455.00},
        {"name":"THM-119","bm":"BM2","spend":2783.63,"purchases":24,"revenue":2015.00},
    ],
}

# ============================================================
# META API (live mode)
# ============================================================
def get_token(bm):
    return BM1_TOKEN if bm == "BM1" else BM2_TOKEN

def fetch_account(account, date_preset):
    token = get_token(account["bm"])
    url = f"{BASE}{account['id']}/insights"
    params = {"fields":"spend,actions,purchase_roas","date_preset":date_preset,"access_token":token}
    try:
        r = requests.get(url, params=params, timeout=30)
        data = r.json().get("data", [])
        if not data:
            return {"name":account["name"],"bm":account["bm"],"spend":0,"purchases":0,"revenue":0}
        row = data[0]
        spend = float(row.get("spend", 0))
        purchases = 0
        for a in row.get("actions", []):
            if a["action_type"] == "offsite_conversion.fb_pixel_purchase":
                purchases = int(a["value"]); break
        roas = 0
        for ri in row.get("purchase_roas", []):
            if ri["action_type"] == "omni_purchase":
                roas = float(ri["value"]); break
        return {"name":account["name"],"bm":account["bm"],"spend":spend,"purchases":purchases,"revenue":round(spend*roas,2)}
    except Exception:
        return {"name":account["name"],"bm":account["bm"],"spend":0,"purchases":0,"revenue":0}

def fetch_all_live(date_preset):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_account, a, date_preset): a for a in ACCOUNTS}
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
    results.sort(key=lambda x: x["spend"], reverse=True)
    return [r for r in results if r["spend"] > 0]

# ============================================================
# FLASK
# ============================================================
app = Flask(__name__)
DATE_MAP = {"today":"today","yesterday":"yesterday","lifetime":"maximum"}

@app.route("/")
def index():
    return render_template_string(HTML, live=LIVE_MODE)

@app.route("/api/data/<period>")
def api_data(period):
    if LIVE_MODE:
        preset = DATE_MAP.get(period, "today")
        rows = fetch_all_live(preset)
    else:
        rows = CACHED.get(period, CACHED["today"])
    return jsonify(rows)


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Meta Ads Dashboard</title>
<style>
:root{
  --bg:#0b0d11;--bg2:#12151c;--border:#1e2230;--text:#e5e7eb;--text2:#9ca3af;--text3:#6b7280;
  --accent:#3b82f6;--green:#22c55e;--red:#ef4444;--card-shadow:0 1px 3px rgba(0,0,0,.3);
}
.light{
  --bg:#f3f4f6;--bg2:#fff;--border:#e5e7eb;--text:#111827;--text2:#4b5563;--text3:#6b7280;
  --card-shadow:0 1px 3px rgba(0,0,0,.08);
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif;background:var(--bg);color:var(--text);line-height:1.5;transition:background .3s,color .3s}

.header{background:var(--bg2);border-bottom:1px solid var(--border);padding:16px 32px;display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:18px;font-weight:700;display:flex;align-items:center;gap:10px}
.header h1 svg{width:22px;height:22px}
.hdr-r{display:flex;align-items:center;gap:16px}
.status{font-size:12px;color:var(--text3);display:flex;align-items:center;gap:6px}
.status .dot{width:7px;height:7px;border-radius:50%;background:var(--green);display:inline-block}
.status.loading .dot{background:#f59e0b;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}


.refresh-btn{width:32px;height:32px;border-radius:8px;border:1px solid var(--border);background:var(--bg2);color:var(--text3);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s}
.refresh-btn:hover{border-color:var(--accent);color:var(--accent)}
.refresh-btn svg{width:16px;height:16px}
.refresh-btn.spinning svg{animation:sp .7s linear infinite}

.theme-t{width:44px;height:24px;background:var(--border);border-radius:12px;cursor:pointer;position:relative;border:none;transition:background .3s}
.theme-t::after{content:'';position:absolute;top:3px;left:3px;width:18px;height:18px;background:var(--accent);border-radius:50%;transition:transform .3s}
.light .theme-t::after{transform:translateX(20px);background:#f59e0b}

.date-f{display:flex;background:var(--bg2);border:1px solid var(--border);border-radius:8px;overflow:hidden}
.date-b{padding:6px 16px;font-size:13px;font-weight:500;color:var(--text3);background:transparent;border:none;cursor:pointer;transition:all .2s}
.date-b:hover{color:var(--text)}.date-b.active{background:var(--accent);color:#fff}
.date-b:disabled{opacity:.5;cursor:not-allowed}

.ctn{max-width:1200px;margin:0 auto;padding:24px 32px}

.sgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}
.scard{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:20px 24px;box-shadow:var(--card-shadow);transition:border-color .2s,background .3s}
.scard:hover{border-color:var(--accent)}
.scard .lbl{font-size:12px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;display:flex;align-items:center;gap:6px}
.scard .lbl svg{width:14px;height:14px;opacity:.7}
.scard .val{font-size:28px;font-weight:700;letter-spacing:-.5px}
.scard .sub{font-size:12px;color:var(--text3);margin-top:2px}
.vg{color:var(--green)}.vr{color:var(--red)}

.tw{background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;box-shadow:var(--card-shadow)}
.th-bar{padding:16px 24px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
.th-bar h2{font-size:14px;font-weight:600}
.th-bar .cnt{font-size:12px;color:var(--text3);background:var(--bg);padding:2px 10px;border-radius:10px}
table{width:100%;border-collapse:collapse}
thead th{text-align:left;padding:10px 16px;font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid var(--border);cursor:pointer;user-select:none;white-space:nowrap}
thead th.num{text-align:right}
thead th:hover{color:var(--text)}
thead th .arrow{font-size:10px;margin-left:4px;opacity:.7;color:var(--accent)}
thead th.sorted{color:var(--accent)}
tbody tr{border-bottom:1px solid var(--border);transition:background .15s}
tbody tr:last-child{border-bottom:none}
tbody tr:hover{background:rgba(59,130,246,.04)}
tbody td{padding:12px 16px;font-size:13px;white-space:nowrap}
tbody td.num{text-align:right;font-variant-numeric:tabular-nums}
.an{font-weight:600;display:flex;align-items:center;gap:8px}
.bm{font-size:10px;font-weight:600;padding:2px 6px;border-radius:4px;background:rgba(59,130,246,.15);color:var(--accent)}
.bm.b2{background:rgba(168,139,250,.15);color:#a78bfa}
.zero{color:var(--text3)}

tfoot tr{border-top:2px solid var(--border);font-weight:700;font-size:13px;background:var(--bg)}
tfoot td{padding:14px 16px}
tfoot td.num{text-align:right;font-variant-numeric:tabular-nums}

.footer{text-align:center;padding:20px;font-size:11px;color:var(--text3)}

.loader{display:none;text-align:center;padding:60px;color:var(--text3);font-size:14px}
.loader.show{display:block}
.loader .spin{display:inline-block;width:24px;height:24px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:sp .7s linear infinite;margin-bottom:12px}
@keyframes sp{to{transform:rotate(360deg)}}

@media(max-width:768px){.sgrid{grid-template-columns:repeat(2,1fr)}.header{padding:12px 16px;flex-wrap:wrap;gap:10px}.ctn{padding:16px}}
</style>
</head>
<body>

<div class="header">
  <h1>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
    Meta Ads Dashboard
  </h1>
  <div class="hdr-r">
    <div class="status" id="status">
      <span class="dot"></span>
      <span id="statusText">Ready</span>
      <span id="lastUpdate" style="margin-left:4px;font-size:11px;color:var(--text3)"></span>
    </div>
    <button class="refresh-btn" onclick="refresh()" title="Refresh now">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
    </button>
    <div class="date-f">
      <button class="date-b active" data-period="today">Today</button>
      <button class="date-b" data-period="yesterday">Yesterday</button>
      <button class="date-b" data-period="lifetime">Lifetime</button>
    </div>
    <button class="theme-t" onclick="document.body.classList.toggle('light')" title="Toggle dark/light"></button>
  </div>
</div>

<div class="ctn">
  <div class="sgrid">
    <div class="scard">
      <div class="lbl">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>
        Sales
      </div>
      <div class="val" id="tSales">--</div>
      <div class="sub">purchases (Meta pixel)</div>
    </div>
    <div class="scard">
      <div class="lbl">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
        Revenue
      </div>
      <div class="val" id="tRev">--</div>
      <div class="sub">from Meta pixel</div>
    </div>
    <div class="scard">
      <div class="lbl">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        Spend
      </div>
      <div class="val" id="tSpend">--</div>
      <div class="sub" id="tSpendSub">across all accounts</div>
    </div>
    <div class="scard">
      <div class="lbl">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
        ROI
      </div>
      <div class="val" id="tROI">--</div>
      <div class="sub">(revenue - spend) / spend</div>
    </div>
  </div>

  <div class="loader" id="loader"><div class="spin"></div><br>Loading data from Meta API...</div>

  <div class="tw" id="tableWrap">
    <div class="th-bar">
      <h2>Account Breakdown</h2>
      <span class="cnt" id="aCnt">--</span>
    </div>
    <table>
      <thead>
        <tr>
          <th data-col="name">Account <span class="arrow"></span></th>
          <th class="num" data-col="purchases">Sales <span class="arrow"></span></th>
          <th class="num" data-col="spend">Spend <span class="arrow"></span></th>
          <th class="num" data-col="revenue">Revenue <span class="arrow"></span></th>
          <th class="num" data-col="profit">Profit <span class="arrow"></span></th>
          <th class="num" data-col="cpa">CPA <span class="arrow"></span></th>
          <th class="num" data-col="roi">ROI <span class="arrow"></span></th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
      <tfoot id="tfoot"></tfoot>
    </table>
  </div>
</div>

<div class="footer">Data from Meta Marketing API v21.0 &middot; BM1: Martha Lucelly 1 &middot; BM2: JV Liminal</div>

<script>
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const fmt = n => "$" + n.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});

let rows = [];
let sortCol = "spend", sortAsc = false;

$$(".date-b").forEach(b => b.addEventListener("click", () => {
  $$(".date-b").forEach(x => x.classList.remove("active"));
  b.classList.add("active");
  loadData(b.dataset.period);
}));

$$("thead th").forEach(th => th.addEventListener("click", () => {
  const col = th.dataset.col;
  if (sortCol === col) sortAsc = !sortAsc;
  else { sortCol = col; sortAsc = col === "name"; }
  renderTable();
}));

function loadData(period) {}

function renderCards() {
  const ts = rows.reduce((s,r) => s + r.spend, 0);
  const tr = rows.reduce((s,r) => s + r.revenue, 0);
  const tp = rows.reduce((s,r) => s + r.purchases, 0);
  const roi = ts > 0 ? ((tr - ts) / ts) * 100 : 0;
  const active = rows.length;

  $("#tSales").textContent = tp.toLocaleString();
  $("#tRev").textContent = fmt(tr);
  $("#tRev").className = "val" + (tr > 0 ? " vg" : "");
  $("#tSpend").textContent = fmt(ts);
  $("#tSpendSub").textContent = active + " accounts spending";

  const re = $("#tROI");
  re.textContent = (roi >= 0 ? "+" : "") + roi.toFixed(1) + "%";
  re.className = "val " + (roi >= 0 ? "vg" : "vr");
}

function renderTable() {
  const sorted = [...rows].sort((a, b) => {
    let va = a[sortCol], vb = b[sortCol];
    if (va === null) va = -Infinity;
    if (vb === null) vb = -Infinity;
    if (typeof va === "string") return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va - vb : vb - va;
  });

  $("#aCnt").textContent = rows.length + " active account" + (rows.length !== 1 ? "s" : "");

  $$("thead th").forEach(th => {
    const arrow = th.querySelector(".arrow");
    if (th.dataset.col === sortCol) {
      arrow.textContent = sortAsc ? " ▲" : " ▼";
      th.classList.add("sorted");
    } else {
      arrow.textContent = "";
      th.classList.remove("sorted");
    }
  });

  $("#tbody").innerHTML = sorted.map(r => `
    <tr>
      <td><div class="an"><span class="bm ${r.bm==='BM2'?'b2':''}">${r.bm}</span>${r.name}</div></td>
      <td class="num ${r.purchases===0?'zero':''}">${r.purchases.toLocaleString()}</td>
      <td class="num">${fmt(r.spend)}</td>
      <td class="num ${r.revenue>0?'vg':'zero'}">${fmt(r.revenue)}</td>
      <td class="num ${r.profit>=0?'vg':'vr'}">${fmt(r.profit)}</td>
      <td class="num ${r.cpa!==null?'':'zero'}">${r.cpa!==null?fmt(r.cpa):'—'}</td>
      <td class="num ${r.roi!==null?(r.roi>=0?'vg':'vr'):'zero'}">${r.roi!==null?(r.roi>=0?'+':'')+r.roi.toFixed(1)+'%':'—'}</td>
    </tr>`).join("");

  const ts = rows.reduce((s,r) => s+r.spend,0);
  const tr = rows.reduce((s,r) => s+r.revenue,0);
  const tp = rows.reduce((s,r) => s+r.purchases,0);
  const tP = tr - ts;
  const tC = tp > 0 ? ts / tp : null;
  const tR = ts > 0 ? ((tr-ts)/ts)*100 : 0;

  $("#tfoot").innerHTML = `
    <tr>
      <td>TOTAL</td>
      <td class="num">${tp.toLocaleString()}</td>
      <td class="num">${fmt(ts)}</td>
      <td class="num ${tr>0?'vg':''}">${fmt(tr)}</td>
      <td class="num ${tP>=0?'vg':'vr'}">${fmt(tP)}</td>
      <td class="num">${tC!==null?fmt(tC):'—'}</td>
      <td class="num ${tR>=0?'vg':'vr'}">${(tR>=0?'+':'')+tR.toFixed(1)}%</td>
    </tr>`;
}

let currentPeriod = "today";
let nextAutoAt = null;
let schedulerTimer = null;
const INTERVAL_MS = 90 * 60 * 1000;
const START_HOUR = 9;
const STOP_HOUR = 20;

function inSchedule() {
  const h = new Date().getHours();
  return h >= START_HOUR && h < STOP_HOUR;
}

function refresh() {
  skipNextAuto();
  doLoad(currentPeriod);
}

function skipNextAuto() {
  if (nextAutoAt) {
    nextAutoAt = new Date(nextAutoAt.getTime() + INTERVAL_MS);
    updateNextLabel();
  }
}

function updateTimestamp() {
  const t = new Date().toLocaleTimeString("en-US", {hour:"2-digit", minute:"2-digit"});
  $("#lastUpdate").textContent = "Last: " + t;
}

function updateNextLabel() {
  if (!inSchedule() || !nextAutoAt) {
    $("#statusText").textContent = "Paused until 9 AM";
    return;
  }
  const t = nextAutoAt.toLocaleTimeString("en-US", {hour:"2-digit", minute:"2-digit"});
  $("#statusText").textContent = "Next: " + t;
}

function scheduleAutos() {
  if (schedulerTimer) clearInterval(schedulerTimer);
  const now = new Date();
  if (inSchedule()) {
    nextAutoAt = new Date(now.getTime() + INTERVAL_MS);
  } else {
    const tomorrow9 = new Date(now);
    tomorrow9.setDate(tomorrow9.getDate() + (now.getHours() >= STOP_HOUR ? 1 : 0));
    tomorrow9.setHours(START_HOUR, 0, 0, 0);
    nextAutoAt = tomorrow9;
  }
  updateNextLabel();

  schedulerTimer = setInterval(() => {
    const now = new Date();
    if (!inSchedule()) { updateNextLabel(); return; }
    if (nextAutoAt && now >= nextAutoAt) {
      nextAutoAt = new Date(now.getTime() + INTERVAL_MS);
      if (nextAutoAt.getHours() >= STOP_HOUR) nextAutoAt = null;
      updateNextLabel();
      doLoad(currentPeriod);
    }
  }, 30000);
}

function doLoad(period) {
  currentPeriod = period;
  $(".refresh-btn").classList.add("spinning");
  $$(".date-b").forEach(b => b.disabled = true);
  $("#status").classList.add("loading");
  $("#loader").classList.add("show");
  $("#tableWrap").style.opacity = "0.3";

  fetch("/api/data/" + period)
    .then(r => r.json())
    .then(data => {
      rows = data.map(r => ({
        ...r,
        profit: r.revenue - r.spend,
        cpa: r.purchases > 0 ? r.spend / r.purchases : null,
        roi: r.spend > 0 ? ((r.revenue - r.spend) / r.spend) * 100 : null,
      }));
      renderCards();
      renderTable();
      finish();
    })
    .catch(() => finish());
}

function finish() {
  $("#status").classList.remove("loading");
  $(".refresh-btn").classList.remove("spinning");
  $("#loader").classList.remove("show");
  $("#tableWrap").style.opacity = "1";
  $$(".date-b").forEach(b => b.disabled = false);
  updateTimestamp();
  updateNextLabel();
}

loadData = doLoad;
doLoad("today");
scheduleAutos();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    mode = "LIVE" if LIVE_MODE else "CACHE"
    print(f"\n  Meta Dashboard ({mode}) -> http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
