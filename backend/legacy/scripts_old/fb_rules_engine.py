"""
FB Rules Engine - Meta Ads Rule Management
Rules are created on Meta's servers via the Ad Rules API.
They run 24/7 on Meta even without this dashboard open.

Usage:
  pip install flask requests
  python fb_rules_engine.py
"""

import os, json, requests
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect

# ============================================================
# CONFIG
# ============================================================
BM1_TOKEN = "YOUR_BM1_TOKEN_HERE"
BM2_TOKEN = "YOUR_BM2_TOKEN_HERE"

API_VERSION = "v21.0"
BASE = f"https://graph.facebook.com/{API_VERSION}/"

ALL_ACCOUNTS = {
    "BM1": {
        "accounts": {
            "MARTHA 2":"act_528756616577904","MARTHA 4":"act_708152401990591",
            "GM-177":"act_1027335185283047","RPG 15":"act_2121935234933980",
            "THM-60":"act_1247132143392586","THM-32":"act_1985532452249785",
            "THM-54":"act_1594785768155717","THM-72":"act_1540233950717702",
            "THM-113":"act_1074066461137769","THM-200":"act_1059904599553927",
        }
    },
    "BM2": {
        "accounts": {
            "DG-03":"act_1306256300004871","DG-51":"act_900364275348331",
            "MSTC-20":"act_1239484177480232","THM-119":"act_1650693448960867",
            "KM-19":"act_2049541032515377","THM-55":"act_1654285161902955",
        }
    }
}

def get_token(bm):
    return BM1_TOKEN if bm == "BM1" else BM2_TOKEN

# ============================================================
# LOCAL STORAGE
# ============================================================
DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE = os.path.join(DIR, "fb_rules.json")
LOG_FILE = os.path.join(DIR, "fb_rules_log.json")

def load_rules():
    if os.path.exists(RULES_FILE):
        with open(RULES_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return []

def save_rules(rules):
    with open(RULES_FILE, "w", encoding="utf-8") as f: json.dump(rules, f, indent=2, ensure_ascii=False)

def load_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return []

def append_log(entry):
    logs = load_logs()
    logs.insert(0, entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f: json.dump(logs[:500], f, indent=2, ensure_ascii=False)

# ============================================================
# META API
# ============================================================
def api_get(ep, token, params=None):
    try:
        r = requests.get(BASE+ep, headers={"Authorization":f"Bearer {token}"}, params=params or {}, timeout=30)
        r.raise_for_status(); return r.json()
    except Exception as e: return {"error":str(e)}

def api_post(ep, token, data=None):
    try:
        r = requests.post(BASE+ep, headers={"Authorization":f"Bearer {token}"}, data=data or {}, timeout=30)
        r.raise_for_status(); return r.json()
    except Exception as e: return {"error":str(e)}

def api_delete(ep, token):
    try:
        r = requests.delete(BASE+ep, headers={"Authorization":f"Bearer {token}"}, timeout=30)
        r.raise_for_status(); return r.json()
    except Exception as e: return {"error":str(e)}

def get_campaigns(account_id, token, status="ACTIVE"):
    params = {"fields":"id,name,status,effective_status",
              "filtering":json.dumps([{"field":"effective_status","operator":"IN","value":[status]}]),"limit":500}
    return api_get(f"{account_id}/campaigns", token, params).get("data", [])

# ============================================================
# META AD RULES API
# ============================================================
METRIC_TO_META = {
    "cpc": "cpc",
    "cpm": "cpm",
    "cpa_checkout": "cost_per_action_type:offsite_conversion.fb_pixel_InitiateCheckout",
    "cpa_purchase": "cost_per_action_type:offsite_conversion.fb_pixel_Purchase",
    "spend": "spent",
    "purchases": "actions:offsite_conversion.fb_pixel_Purchase",
    "checkouts": "actions:offsite_conversion.fb_pixel_InitiateCheckout",
    "days_running": "hours_since_creation",
}
OP_TO_META = {">":"GREATER_THAN",">=":"GREATER_THAN","<":"LESS_THAN","<=":"LESS_THAN","==":"EQUAL"}
TIME_RANGE_META = {"today":"TODAY","last_3d":"LAST_3_DAYS","last_7d":"LAST_7_DAYS","lifetime":"LIFETIME"}
FREQ_META = {"30min":"SEMI_HOURLY","1h":"HOURLY","4h":"EVERY_4_HOURS","6h":"EVERY_6_HOURS","12h":"EVERY_12_HOURS","24h":"DAILY"}

def create_meta_rule(account_id, token, rule):
    name = rule["name"]

    if rule["type"] == "schedule":
        exec_type = "PAUSE_CAMPAIGN" if rule["action"] == "PAUSE" else "UNPAUSE_CAMPAIGN"
        start_min = rule["hour"] * 60 + rule.get("min", 0)
        data = {
            "name": name,
            "evaluation_spec": json.dumps({"evaluation_type":"SCHEDULE","filters":[
                {"field":"entity_type","value":"CAMPAIGN","operator":"EQUAL"},
                {"field":"id","value":rule["campaign_ids"],"operator":"IN"},
            ]}),
            "execution_spec": json.dumps({"execution_type": exec_type}),
            "schedule_spec": json.dumps({"schedule_type":"CUSTOM",
                "schedule":[{"days":[0,1,2,3,4,5,6],"start_minute":start_min,"end_minute":start_min}]}),
        }

    elif rule["type"] == "condition":
        exec_type = "PAUSE_ADSET" if rule["action"] == "PAUSE" else "UNPAUSE_ADSET"
        time_preset = TIME_RANGE_META.get(rule.get("time_range", "last_3d"), "LAST_3_DAYS")
        freq = FREQ_META.get(rule.get("check_freq", "30min"), "SEMI_HOURLY")

        filters = [
            {"field":"entity_type","value":"ADSET","operator":"EQUAL"},
            {"field":"campaign.id","value":rule["campaign_ids"],"operator":"IN"},
            {"field":"time_preset","value":time_preset,"operator":"EQUAL"},
        ]

        for cond in rule.get("conditions", []):
            m = cond["metric"]
            meta_field = METRIC_TO_META.get(m, m)
            meta_op = OP_TO_META.get(cond["op"], "GREATER_THAN")
            val = cond["val"]
            if m == "days_running":
                val = val * 24
            filters.append({"field": meta_field, "value": val, "operator": meta_op})

        data = {
            "name": name,
            "evaluation_spec": json.dumps({"evaluation_type":"SCHEDULE","filters":filters}),
            "execution_spec": json.dumps({"execution_type": exec_type}),
            "schedule_spec": json.dumps({"schedule_type": freq}),
        }
    else:
        return {"error": "Unknown type"}

    result = api_post(f"{account_id}/adrules_library", token, data=data)
    append_log({"ts":datetime.now().strftime("%Y-%m-%d %H:%M"),"rule":name,"action":"CREATED ON META",
                "ok":"id" in result,"detail":"OK" if "id" in result else str(result.get("error","")),"campaign":rule.get("account_name","")})
    return result

def toggle_meta_rule(meta_rule_id, token, enabled):
    return api_post(meta_rule_id, token, data={"status":"ENABLED" if enabled else "PAUSED"})

def delete_meta_rule(meta_rule_id, token):
    return api_delete(meta_rule_id, token)

# ============================================================
# PRESETS (10 rules) - now with conditions arrays
# ============================================================
PRESETS = [
    {"id":"pause_11pm","name":"Pause at 11:00 PM","name_es":"Pausar a las 11:00 PM",
     "desc":"Stop overnight spend","desc_es":"Detener gasto nocturno",
     "help":"Pauses all selected campaigns at 11PM every night to prevent spending while you sleep.",
     "help_es":"Pausa todas las campanas a las 11PM cada noche para evitar gastar mientras duermes.",
     "type":"schedule","action":"PAUSE","hour":23,"min":0,"icon":"moon"},

    {"id":"activate_12pm","name":"Activate at 12:00 PM","name_es":"Activar a las 12:00 PM",
     "desc":"Resume spending at noon","desc_es":"Reanudar gasto al mediodia",
     "help":"Turns on all selected campaigns at noon every day.",
     "help_es":"Activa todas las campanas al mediodia cada dia.",
     "type":"schedule","action":"ACTIVATE","hour":12,"min":0,"icon":"sun"},

    {"id":"pause_6am","name":"Pause at 6:00 AM","name_es":"Pausar a las 6:00 AM",
     "desc":"Stop early morning spend","desc_es":"Detener gasto de madrugada",
     "help":"Pauses campaigns at 6AM.",
     "help_es":"Pausa campanas a las 6AM.",
     "type":"schedule","action":"PAUSE","hour":6,"min":0,"icon":"sunrise"},

    {"id":"activate_8am","name":"Activate at 8:00 AM","name_es":"Activar a las 8:00 AM",
     "desc":"Start the day","desc_es":"Iniciar el dia",
     "help":"Activates campaigns at 8AM.",
     "help_es":"Activa campanas a las 8AM.",
     "type":"schedule","action":"ACTIVATE","hour":8,"min":0,"icon":"play"},

    {"id":"kill_cpa_co","name":"Kill CPA CO > $20","name_es":"Matar CPA CO > $20",
     "desc":"Pause if checkout CPA too high","desc_es":"Pausar si CPA checkout muy alto",
     "help":"If CPA Checkout > $20 AND Spend > $50, pause the adset.",
     "help_es":"Si CPA Checkout > $20 Y Gasto > $50, pausar el adset.",
     "type":"condition","action":"PAUSE","time_range":"last_3d","check_freq":"30min",
     "conditions":[{"metric":"cpa_checkout","op":">","val":20},{"metric":"spend","op":">","val":50}],
     "icon":"x-circle"},

    {"id":"kill_cpc_150","name":"Kill CPC > $1.50","name_es":"Matar CPC > $1.50",
     "desc":"Pause if CPC exceeds $1.50","desc_es":"Pausar si CPC supera $1.50",
     "help":"If CPC > $1.50 AND Spend > $10, pause the adset (video ads).",
     "help_es":"Si CPC > $1.50 Y Gasto > $10, pausar el adset (anuncios de video).",
     "type":"condition","action":"PAUSE","time_range":"last_3d","check_freq":"30min",
     "conditions":[{"metric":"cpc","op":">","val":1.5},{"metric":"spend","op":">","val":10}],
     "icon":"trending-down"},

    {"id":"kill_cpc_100","name":"Kill CPC > $1.00","name_es":"Matar CPC > $1.00",
     "desc":"Pause if CPC exceeds $1.00","desc_es":"Pausar si CPC supera $1.00",
     "help":"If CPC > $1.00 AND Spend > $10, pause the adset (image ads).",
     "help_es":"Si CPC > $1.00 Y Gasto > $10, pausar el adset (anuncios de imagen).",
     "type":"condition","action":"PAUSE","time_range":"last_3d","check_freq":"30min",
     "conditions":[{"metric":"cpc","op":">","val":1.0},{"metric":"spend","op":">","val":10}],
     "icon":"trending-down"},

    {"id":"pause_no_spend","name":"Pause $0 Spend (3d)","name_es":"Pausar $0 Gasto (3d)",
     "desc":"Pause if no spend for 3 days","desc_es":"Pausar si no gasta en 3 dias",
     "help":"If Spend < $0.01 over last 3 days AND Days Running >= 3, pause.",
     "help_es":"Si Gasto < $0.01 en 3 dias Y Dias corriendo >= 3, pausar.",
     "type":"condition","action":"PAUSE","time_range":"last_3d","check_freq":"30min",
     "conditions":[{"metric":"spend","op":"<","val":0.01},{"metric":"days_running","op":">=","val":3}],
     "icon":"alert"},

    {"id":"no_purchase_3d","name":"No Purchase 3 Days","name_es":"Sin Venta 3 Dias",
     "desc":"Pause if 0 purchases after 3 days","desc_es":"Pausar si 0 ventas en 3 dias",
     "help":"If Purchases < 1 AND Days Running >= 3 AND Spend > $5, pause.",
     "help_es":"Si Compras < 1 Y Dias corriendo >= 3 Y Gasto > $5, pausar.",
     "type":"condition","action":"PAUSE","time_range":"last_3d","check_freq":"30min",
     "conditions":[{"metric":"purchases","op":"<","val":1},{"metric":"days_running","op":">=","val":3},{"metric":"spend","op":">","val":5}],
     "icon":"slash"},

    {"id":"budget_bump","name":"Budget $1 -> $1.05","name_es":"Presupuesto $1 -> $1.05",
     "desc":"Bump budget if not spending","desc_es":"Subir presupuesto si no gasta",
     "help":"If Spend = $0 AND Days Running >= 1, indicates adset is stuck. Requires manual budget bump.",
     "help_es":"Si Gasto = $0 Y Dias corriendo >= 1, indica que el adset esta trabado. Requiere bump manual.",
     "type":"condition","action":"PAUSE","time_range":"last_3d","check_freq":"30min",
     "conditions":[{"metric":"spend","op":"<","val":0.01},{"metric":"days_running","op":">=","val":1}],
     "icon":"dollar"},
]

# ============================================================
# FLASK
# ============================================================
app = Flask(__name__)

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rules Engine</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0b0d11;color:#d1d5db;line-height:1.5}

.hdr{background:#12151c;border-bottom:1px solid #1e2230;padding:14px 28px;display:flex;justify-content:space-between;align-items:center}
.hdr h1{font-size:16px;font-weight:600;color:#f3f4f6}
.hdr-r{display:flex;align-items:center;gap:16px}
.hdr span{font-size:12px;color:#6b7280}
.lang-t{display:flex;background:#1e2230;border-radius:6px;overflow:hidden;border:1px solid #2a2e3d}
.lang-b{padding:4px 12px;font-size:11px;font-weight:600;border:none;cursor:pointer;background:transparent;color:#6b7280}
.lang-b.active{background:#3b82f6;color:#fff}

.ctn{max-width:1100px;margin:0 auto;padding:24px}
.tabs{display:flex;gap:4px;margin-bottom:24px;background:#12151c;border-radius:10px;padding:4px;border:1px solid #1e2230}
.tab{flex:1;text-align:center;padding:10px;font-size:13px;font-weight:500;color:#6b7280;border-radius:8px;cursor:pointer;border:none;background:none}
.tab:hover{color:#d1d5db}.tab.active{background:#1e2230;color:#fff}
.tc{display:none}.tc.active{display:block}

.card{background:#12151c;border:1px solid #1e2230;border-radius:10px;padding:16px;margin-bottom:10px;transition:border-color .2s;position:relative}
.card:hover{border-color:#374151}.card.ck{cursor:pointer}.card.sel{border-color:#3b82f6;box-shadow:0 0 0 1px #3b82f6}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:768px){.g2,.split{grid-template-columns:1fr !important}}

.pre{display:flex;align-items:center;gap:12px}
.pre-e{width:44px;height:44px;display:flex;align-items:center;justify-content:center;background:#1e2230;border-radius:10px;flex-shrink:0}
.ico{width:22px;height:22px;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;fill:none}
.ico-moon{stroke:#a78bfa}.ico-sun{stroke:#fbbf24}.ico-sunrise{stroke:#f97316}.ico-play{stroke:#34d399}
.ico-x-circle{stroke:#f87171}.ico-trending-down{stroke:#f87171}.ico-alert{stroke:#fbbf24}
.ico-slash{stroke:#f87171}.ico-dollar{stroke:#60a5fa}
.pre-i h3{font-size:14px;font-weight:600;color:#f3f4f6;margin-bottom:2px}
.pre-i p{font-size:12px;color:#6b7280}

.hi{position:absolute;top:10px;right:10px;width:20px;height:20px;border-radius:50%;background:#1e2230;border:1px solid #2a2e3d;display:flex;align-items:center;justify-content:center;font-size:11px;color:#6b7280;cursor:help;z-index:2}
.hi:hover{background:#2a2e3d;color:#f3f4f6}
.tt{display:none;position:absolute;top:32px;right:0;background:#1a1d27;border:1px solid #3b82f6;border-radius:8px;padding:10px 12px;font-size:12px;color:#d1d5db;width:280px;z-index:10;line-height:1.4;box-shadow:0 4px 12px rgba(0,0,0,.4)}
.hi:hover .tt{display:block}

.tag{display:inline-block;font-size:11px;font-weight:600;padding:3px 8px;border-radius:4px}
.t-p{background:#7f1d1d;color:#fca5a5}.t-a{background:#14532d;color:#86efac}
.t-s{background:#312e81;color:#c4b5fd}.t-c{background:#78350f;color:#fcd34d}
.t-b{background:#1e3a5f;color:#93c5fd}.t-cu{background:#1e2230;color:#93c5fd}
.meta-b{display:inline-block;font-size:10px;padding:2px 6px;border-radius:3px;background:#14532d;color:#86efac;margin-left:6px}

.pnl{background:#12151c;border:1px solid #1e2230;border-radius:10px;padding:20px}
.pnl-t{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;margin-bottom:12px}

select,input[type=text],input[type=number]{width:100%;padding:8px 12px;background:#1a1d27;border:1px solid #2a2e3d;border-radius:6px;color:#f3f4f6;font-size:13px}
select:focus,input:focus{outline:none;border-color:#3b82f6}
label{font-size:12px;color:#9ca3af;margin-bottom:4px;display:block}

.btn{padding:8px 16px;border-radius:6px;font-size:13px;font-weight:600;border:none;cursor:pointer}
.btn-p{background:#3b82f6;color:#fff;width:100%;padding:12px}.btn-p:hover{background:#2563eb}
.btn-s{padding:5px 10px;font-size:12px}
.btn-g{background:transparent;color:#9ca3af;border:1px solid #2a2e3d}.btn-g:hover{background:#1e2230;color:#f3f4f6}
.btn-d{background:transparent;color:#ef4444;border:1px solid #7f1d1d}.btn-d:hover{background:#7f1d1d}
.btn-ok{background:transparent;color:#22c55e;border:1px solid #14532d}.btn-ok:hover{background:#14532d}

.cl{max-height:300px;overflow-y:auto}
.ci{display:flex;align-items:center;gap:8px;padding:8px 10px;border-bottom:1px solid #1e2230;font-size:13px}
.ci:last-child{border-bottom:none}.ci input[type=checkbox]{accent-color:#3b82f6}
.cn{color:#f3f4f6}.cid{color:#6b7280;font-size:11px}

.split{display:grid;grid-template-columns:1fr 380px;gap:20px}
.step{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#3b82f6;color:#fff;font-size:11px;font-weight:700;margin-right:6px}
.fr{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:12px}
.fg{display:flex;flex-direction:column;gap:4px}

/* Condition row */
.cond-row{display:grid;grid-template-columns:1fr 100px 100px 40px;gap:8px;align-items:end;margin-bottom:8px;padding:10px;background:#0f1117;border:1px solid #1e2230;border-radius:8px}
.cond-row .fg{margin:0}
.cond-rm{width:32px;height:32px;border-radius:6px;background:transparent;border:1px solid #7f1d1d;color:#ef4444;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:14px}
.cond-rm:hover{background:#7f1d1d}
.add-cond{display:flex;align-items:center;gap:6px;background:transparent;border:1px dashed #2a2e3d;border-radius:8px;padding:10px;color:#6b7280;cursor:pointer;width:100%;font-size:13px;justify-content:center;margin-bottom:12px}
.add-cond:hover{border-color:#3b82f6;color:#3b82f6}
.and-label{text-align:center;font-size:11px;font-weight:700;color:#3b82f6;margin-bottom:8px;text-transform:uppercase}

.dot{width:6px;height:6px;border-radius:50%;display:inline-block}
.dot-on{background:#22c55e;box-shadow:0 0 4px #22c55e}.dot-off{background:#6b7280}
.rr{display:flex;justify-content:space-between;align-items:center}
.rl{display:flex;align-items:center;gap:10px}
.rm{font-size:12px;color:#6b7280;margin-top:6px}
.rc span{display:inline-block;background:#1e2230;color:#9ca3af;font-size:11px;padding:2px 8px;border-radius:4px;margin:2px 2px 2px 0}
.ra{display:flex;gap:4px}
.conds-display{margin-top:4px;font-size:11px;color:#fcd34d}

.lr{padding:8px 12px;border-bottom:1px solid #1e2230;font-size:12px;display:flex;justify-content:space-between}
.l-ok{border-left:2px solid #22c55e}.l-err{border-left:2px solid #ef4444}
.lt{color:#6b7280;white-space:nowrap}

.empty{text-align:center;padding:48px;color:#6b7280}
.bulk-bar{display:flex;justify-content:space-between;align-items:center;background:#12151c;border:1px solid #1e2230;border-radius:8px;padding:10px 16px;margin-bottom:16px}
.bulk-bar label{margin:0;display:flex;align-items:center;gap:6px;font-size:13px;color:#9ca3af}
</style>
</head>
<body>

<svg style="display:none">
  <symbol id="i-moon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor"/></symbol>
  <symbol id="i-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5" stroke="currentColor"/><line x1="12" y1="1" x2="12" y2="3" stroke="currentColor"/><line x1="12" y1="21" x2="12" y2="23" stroke="currentColor"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor"/><line x1="1" y1="12" x2="3" y2="12" stroke="currentColor"/><line x1="21" y1="12" x2="23" y2="12" stroke="currentColor"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="currentColor"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="currentColor"/></symbol>
  <symbol id="i-sunrise" viewBox="0 0 24 24"><path d="M17 18a5 5 0 0 0-10 0" stroke="currentColor"/><line x1="12" y1="9" x2="12" y2="2" stroke="currentColor"/><line x1="4.22" y1="10.22" x2="5.64" y2="11.64" stroke="currentColor"/><line x1="1" y1="18" x2="3" y2="18" stroke="currentColor"/><line x1="21" y1="18" x2="23" y2="18" stroke="currentColor"/><line x1="18.36" y1="11.64" x2="19.78" y2="10.22" stroke="currentColor"/><line x1="23" y1="22" x2="1" y2="22" stroke="currentColor"/><polyline points="8 6 12 2 16 6" stroke="currentColor"/></symbol>
  <symbol id="i-play" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3" stroke="currentColor"/></symbol>
  <symbol id="i-x-circle" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor"/><line x1="15" y1="9" x2="9" y2="15" stroke="currentColor"/><line x1="9" y1="9" x2="15" y2="15" stroke="currentColor"/></symbol>
  <symbol id="i-trending-down" viewBox="0 0 24 24"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6" stroke="currentColor"/><polyline points="17 18 23 18 23 12" stroke="currentColor"/></symbol>
  <symbol id="i-alert" viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" stroke="currentColor"/><line x1="12" y1="9" x2="12" y2="13" stroke="currentColor"/><line x1="12" y1="17" x2="12.01" y2="17" stroke="currentColor"/></symbol>
  <symbol id="i-slash" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" stroke="currentColor"/></symbol>
  <symbol id="i-dollar" viewBox="0 0 24 24"><line x1="12" y1="1" x2="12" y2="23" stroke="currentColor"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" stroke="currentColor"/></symbol>
  <symbol id="i-clock" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor"/><polyline points="12 6 12 12 16 14" stroke="currentColor"/></symbol>
  <symbol id="i-bar-chart" viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10" stroke="currentColor"/><line x1="12" y1="20" x2="12" y2="4" stroke="currentColor"/><line x1="6" y1="20" x2="6" y2="14" stroke="currentColor"/></symbol>
</svg>
<div class="hdr">
  <h1>Rules Engine</h1>
  <div class="hdr-r">
    <span>{{ now }}</span>
    <div class="lang-t">
      <button class="lang-b active" id="lEN" onclick="setLang('en')">EN</button>
      <button class="lang-b" id="lES" onclick="setLang('es')">ES</button>
    </div>
  </div>
</div>

<div class="ctn">
  <div class="tabs">
    <button class="tab active" onclick="showTab('presets',this)" data-en="Presets" data-es="Predeterminadas">Presets</button>
    <button class="tab" onclick="showTab('custom',this)" data-en="+ New Rule" data-es="+ Nueva Regla">+ New Rule</button>
    <button class="tab" onclick="showTab('active',this)" data-en="My Rules ({{ rules|length }})" data-es="Mis Reglas ({{ rules|length }})">My Rules ({{ rules|length }})</button>
    <button class="tab" onclick="showTab('logs',this)" data-en="Log" data-es="Registro">Log</button>
  </div>

  <!-- ==================== PRESETS ==================== -->
  <div class="tc active" id="presets">
    <div class="split">
      <div>
        <div class="g2">
          {% for p in presets %}
          <div class="card ck {% if loop.first %}sel{% endif %}" id="pc_{{ p.id }}" onclick="pickPreset('{{ p.id }}')">
            <div class="hi">?<div class="tt" data-en="{{ p.help }}" data-es="{{ p.help_es }}">{{ p.help }}</div></div>
            <div class="pre">
              <div class="pre-e"><svg class="ico ico-{{ p.icon }}" viewBox="0 0 24 24"><use href="#i-{{ p.icon }}"/></svg></div>
              <div class="pre-i">
                <h3 data-en="{{ p.name }}" data-es="{{ p.name_es }}">{{ p.name }}</h3>
                <p data-en="{{ p.desc }}" data-es="{{ p.desc_es }}">{{ p.desc }}</p>
                <div style="margin-top:6px">
                  <span class="tag {% if p.action=='PAUSE' %}t-p{% elif p.action=='ACTIVATE' %}t-a{% else %}t-b{% endif %}">{{ p.action }}</span>
                  <span class="tag {% if p.type=='schedule' %}t-s{% else %}t-c{% endif %}">{{ p.type|upper }}</span>
                </div>
              </div>
            </div>
          </div>
          {% endfor %}
        </div>
      </div>
      <div>
        <div class="pnl">
          <div class="pnl-t" id="ppT" data-en="Configure Rule" data-es="Configurar Regla">Configure Rule</div>
          <form action="/create_rule" method="POST">
            <input type="hidden" name="source" value="preset">
            <input type="hidden" name="preset_id" id="fPid">
            <div class="fg" style="margin-bottom:12px">
              <label data-en="Ad Account" data-es="Cuenta Publicitaria">Ad Account</label>
              <select name="account" id="aSel" onchange="loadC('aSel','cL')">
                <option value="">Choose account...</option>
                {% for bm,bd in accounts.items() %}<optgroup label="{{ bm }}">{% for n,aid in bd.accounts.items() %}<option value="{{ bm }}|{{ aid }}|{{ n }}">{{ n }}</option>{% endfor %}</optgroup>{% endfor %}
              </select>
            </div>
            <div class="fg" style="margin-bottom:8px">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <label style="margin:0" data-en="Campaigns" data-es="Campanas">Campaigns</label>
                <div><button type="button" class="btn btn-s btn-g" onclick="togAll('cL',1)">All</button> <button type="button" class="btn btn-s btn-g" onclick="togAll('cL',0)">None</button></div>
              </div>
              <div class="card" style="padding:0;margin-top:4px"><div class="cl" id="cL"><div class="empty" style="padding:24px"><p>Select an account</p></div></div></div>
            </div>
            <div class="fg" style="margin-bottom:16px">
              <label data-en="Name (optional)" data-es="Nombre (opcional)">Name (optional)</label>
              <input type="text" name="custom_name" placeholder="e.g. THM-113 Night Pause">
            </div>
            <button type="submit" class="btn btn-p" data-en="Activate Rule on Meta" data-es="Activar Regla en Meta">Activate Rule on Meta</button>
            <div style="text-align:center;margin-top:8px;font-size:11px;color:#6b7280" data-en="Rule will run 24/7 on Meta's servers" data-es="La regla correra 24/7 en los servidores de Meta">Rule will run 24/7 on Meta's servers</div>
          </form>
        </div>
      </div>
    </div>
  </div>

  <!-- ==================== CUSTOM RULE ==================== -->
  <div class="tc" id="custom">
    <form action="/create_rule" method="POST" id="customForm">
      <input type="hidden" name="source" value="custom">

      <!-- Step 1: Type -->
      <div class="pnl" style="margin-bottom:12px">
        <div class="pnl-t"><span class="step">1</span> <span data-en="Rule Type" data-es="Tipo de Regla">Rule Type</span></div>
        <div class="g2">
          <div class="card ck" id="tSch" onclick="pickType('schedule')" style="text-align:center">
            <div style="margin-bottom:8px"><svg class="ico ico-sun" viewBox="0 0 24 24" style="width:32px;height:32px;stroke:#a78bfa"><use href="#i-clock"/></svg></div>
            <strong style="font-size:14px;color:#f3f4f6" data-en="Schedule" data-es="Horario">Schedule</strong>
            <p style="font-size:12px;color:#6b7280" data-en="Pause or activate at a specific time" data-es="Pausar o activar a una hora especifica">Pause or activate at a specific time</p>
          </div>
          <div class="card ck" id="tCon" onclick="pickType('condition')" style="text-align:center">
            <div style="margin-bottom:8px"><svg class="ico" viewBox="0 0 24 24" style="width:32px;height:32px;stroke:#60a5fa"><use href="#i-bar-chart"/></svg></div>
            <strong style="font-size:14px;color:#f3f4f6" data-en="Condition" data-es="Condicion">Condition</strong>
            <p style="font-size:12px;color:#6b7280" data-en="Check metrics and act automatically" data-es="Verificar metricas y actuar automaticamente">Check metrics and act automatically</p>
          </div>
        </div>
        <input type="hidden" name="custom_type" id="cType">
      </div>

      <!-- Step 2: Details -->
      <div class="pnl" style="margin-bottom:12px;display:none" id="cDet">
        <div class="pnl-t"><span class="step">2</span> <span data-en="Details" data-es="Detalles">Details</span></div>

        <!-- Schedule fields -->
        <div id="schF" style="display:none">
          <div class="fr">
            <div class="fg"><label data-en="Action" data-es="Accion">Action</label>
              <select name="custom_action"><option value="PAUSE">Pause</option><option value="ACTIVATE">Activate</option></select></div>
            <div class="fg"><label data-en="Hour" data-es="Hora">Hour</label>
              <select name="custom_hour">{% for h in range(24) %}<option value="{{ h }}" {% if h==23 %}selected{% endif %}>{{ '%02d'|format(h) }}:00</option>{% endfor %}</select></div>
            <div class="fg"><label data-en="Minute" data-es="Minuto">Minute</label>
              <select name="custom_minute"><option value="0">:00</option><option value="15">:15</option><option value="30">:30</option><option value="45">:45</option></select></div>
          </div>
        </div>

        <!-- Condition fields -->
        <div id="conF" style="display:none">
          <!-- Config row -->
          <div class="fr" style="margin-bottom:16px">
            <div class="fg"><label data-en="Time Range" data-es="Rango de Tiempo">Time Range</label>
              <select name="time_range">
                <option value="today" data-en="Today" data-es="Hoy">Today</option>
                <option value="last_3d" selected data-en="Last 3 Days" data-es="Ultimos 3 Dias">Last 3 Days</option>
                <option value="last_7d" data-en="Last 7 Days" data-es="Ultimos 7 Dias">Last 7 Days</option>
                <option value="lifetime" data-en="Lifetime" data-es="Todo el Tiempo">Lifetime</option>
              </select></div>
            <div class="fg"><label data-en="Check Every" data-es="Revisar Cada">Check Every</label>
              <select name="check_freq">
                <option value="30min">30 min</option>
                <option value="1h">1 hora</option>
                <option value="4h">4 horas</option>
                <option value="6h">6 horas</option>
                <option value="12h">12 horas</option>
                <option value="24h">24 horas</option>
              </select></div>
            <div class="fg"><label data-en="Action" data-es="Accion">Action</label>
              <select name="custom_action_condition">
                <option value="PAUSE" data-en="Pause Adsets" data-es="Pausar Adsets">Pause Adsets</option>
                <option value="ACTIVATE" data-en="Activate Adsets" data-es="Activar Adsets">Activate Adsets</option>
              </select></div>
          </div>

          <!-- Conditions builder -->
          <div class="pnl-t" data-en="CONDITIONS (all must be true)" data-es="CONDICIONES (todas deben cumplirse)">CONDITIONS (all must be true)</div>

          <div id="condRows">
            <!-- First condition row (always present) -->
            <div class="cond-row" id="cond_0">
              <div class="fg">
                <label data-en="Metric" data-es="Metrica">Metric</label>
                <select name="cond_metric">
                  <option value="cpc">CPC</option>
                  <option value="cpm">CPM</option>
                  <option value="cpa_checkout">CPA Checkout</option>
                  <option value="cpa_purchase">CPA Purchase</option>
                  <option value="spend" data-en="Spend" data-es="Gasto">Spend</option>
                  <option value="purchases" data-en="Purchases" data-es="Ventas">Purchases</option>
                  <option value="checkouts">Checkouts</option>
                  <option value="days_running" data-en="Days Running" data-es="Dias Corriendo">Days Running</option>
                </select>
              </div>
              <div class="fg">
                <label data-en="Operator" data-es="Operador">Operator</label>
                <select name="cond_op">
                  <option value=">">&gt;</option>
                  <option value=">=">&ge;</option>
                  <option value="<">&lt;</option>
                  <option value="<=">&le;</option>
                  <option value="==">=</option>
                </select>
              </div>
              <div class="fg">
                <label data-en="Value" data-es="Valor">Value</label>
                <input type="number" step="0.01" name="cond_val" value="20">
              </div>
              <div></div>
            </div>
          </div>

          <button type="button" class="add-cond" onclick="addCondition()">
            + <span data-en="Add Condition (AND)" data-es="Agregar Condicion (Y)">Add Condition (AND)</span>
          </button>
        </div>
      </div>

      <!-- Step 3: Account & Campaigns -->
      <div class="pnl" style="margin-bottom:12px;display:none" id="cCam">
        <div class="pnl-t"><span class="step">3</span> <span data-en="Account & Campaigns" data-es="Cuenta y Campanas">Account & Campaigns</span></div>
        <div class="fg" style="margin-bottom:8px">
          <select name="account" id="aSel2" onchange="loadC('aSel2','cL2')">
            <option value="">Choose account...</option>
            {% for bm,bd in accounts.items() %}<optgroup label="{{ bm }}">{% for n,aid in bd.accounts.items() %}<option value="{{ bm }}|{{ aid }}|{{ n }}">{{ n }}</option>{% endfor %}</optgroup>{% endfor %}
          </select>
        </div>
        <div class="card" style="padding:0"><div class="cl" id="cL2"><div class="empty" style="padding:24px"><p>Select an account</p></div></div></div>
      </div>

      <!-- Step 4: Name & Save -->
      <div class="pnl" style="display:none" id="cSub">
        <div class="pnl-t"><span class="step">4</span> <span data-en="Name & Save" data-es="Nombre y Guardar">Name & Save</span></div>
        <div class="fg" style="margin-bottom:12px"><input type="text" name="custom_name" placeholder="Rule name..." required></div>
        <button type="submit" class="btn btn-p" data-en="Create Rule on Meta" data-es="Crear Regla en Meta">Create Rule on Meta</button>
      </div>
    </form>
  </div>

  <!-- ==================== MY RULES ==================== -->
  <div class="tc" id="active">
    {% if rules %}
    <div class="bulk-bar">
      <label><input type="checkbox" id="selAll" onchange="toggleSelectAll()" style="accent-color:#3b82f6"> <span data-en="Select All" data-es="Seleccionar Todas">Select All</span></label>
      <div style="display:flex;gap:6px">
        <form action="/bulk_toggle" method="POST" id="bTog"><input type="hidden" name="rule_ids" id="bTogIds"><input type="hidden" name="action" value="pause">
          <button type="button" class="btn btn-s btn-d" onclick="bulkAction('bTog','pause')" data-en="Pause Selected" data-es="Pausar Seleccionadas">Pause Selected</button></form>
        <form action="/bulk_toggle" method="POST" id="bAct"><input type="hidden" name="rule_ids" id="bActIds"><input type="hidden" name="action" value="activate">
          <button type="button" class="btn btn-s btn-ok" onclick="bulkAction('bAct','activate')" data-en="Activate Selected" data-es="Activar Seleccionadas">Activate Selected</button></form>
        <form action="/bulk_delete" method="POST" id="bDel"><input type="hidden" name="rule_ids" id="bDelIds">
          <button type="button" class="btn btn-s btn-d" onclick="bulkAction('bDel','delete')" data-en="Delete Selected" data-es="Eliminar Seleccionadas">Delete Selected</button></form>
      </div>
    </div>
    {% for r in rules %}
    <div class="card" style="margin-bottom:10px">
      <div class="rr">
        <div class="rl">
          <input type="checkbox" class="rule-cb" value="{{ r.id }}" style="accent-color:#3b82f6">
          <div class="dot {% if r.enabled %}dot-on{% else %}dot-off{% endif %}"></div>
          <div>
            <strong style="color:#f3f4f6;font-size:14px">{{ r.name }}</strong>
            <span class="tag {% if r.action=='PAUSE' %}t-p{% elif r.action=='ACTIVATE' %}t-a{% else %}t-b{% endif %}" style="margin-left:6px">{{ r.action }}</span>
            {% if r.type == 'schedule' %}<span class="tag t-s" style="margin-left:2px">{{ '%02d'|format(r.hour) }}:{{ '%02d'|format(r.get('min',0)) }}</span>{% endif %}
            {% if r.get('is_custom') %}<span class="tag t-cu" style="margin-left:2px">CUSTOM</span>{% endif %}
            {% if r.get('meta_rule_id') %}<span class="meta-b">META &#10003;</span>{% endif %}
          </div>
        </div>
        <div class="ra">
          <form action="/toggle_rule" method="POST" style="display:inline"><input type="hidden" name="rule_id" value="{{ r.id }}"><button class="btn btn-s {% if r.enabled %}btn-d{% else %}btn-ok{% endif %}">{% if r.enabled %}Pause{% else %}Start{% endif %}</button></form>
          <form action="/delete_rule" method="POST" style="display:inline" onsubmit="return confirm('Delete?')"><input type="hidden" name="rule_id" value="{{ r.id }}"><button class="btn btn-s btn-d">&#10005;</button></form>
        </div>
      </div>
      <div class="rm">{{ r.account_name }} &middot; {{ r.campaign_ids|length }} campaigns &middot; {{ r.type }}{% if r.get('check_freq') %} &middot; every {{ r.check_freq }}{% endif %}</div>
      {% if r.get('conditions') %}
      <div class="conds-display">
        {% for c in r.conditions %}{{ c.metric }} {{ c.op }} {{ c.val }}{% if not loop.last %} <span style="color:#3b82f6">AND</span> {% endif %}{% endfor %}
      </div>
      {% endif %}
      <div class="rc" style="margin-top:4px">{% for cid,cn in r.campaign_names.items() %}<span>{{ cn }}</span>{% endfor %}</div>
    </div>
    {% endfor %}
    {% else %}
    <div class="empty"><p style="font-size:28px">&#128203;</p><p>No rules yet.</p></div>
    {% endif %}
  </div>

  <!-- ==================== LOGS ==================== -->
  <div class="tc" id="logs">
    {% if logs %}
    <div style="margin-bottom:12px"><form action="/clear_logs" method="POST" style="display:inline" onsubmit="return confirm('Clear?')"><button class="btn btn-s btn-d">Clear</button></form></div>
    <div class="card" style="padding:0">
      {% for l in logs[:80] %}
      <div class="lr {% if l.ok %}l-ok{% else %}l-err{% endif %}">
        <div>{% if l.ok %}&#9989;{% else %}&#10060;{% endif %} <strong>{{ l.rule }}</strong> &rarr; {{ l.action }} &middot; {{ l.campaign }}
          {% if l.get('detail') and l.detail != 'OK' %}<div style="font-size:11px;margin-top:2px;color:{% if l.ok %}#fbbf24{% else %}#ef4444{% endif %}">{{ l.detail }}</div>{% endif %}
        </div>
        <span class="lt">{{ l.ts }}</span>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <div class="empty"><p style="font-size:28px">&#128196;</p><p>No activity yet.</p></div>
    {% endif %}
  </div>
</div>

<script>
const P={{ presets_json|safe }};
let lang='en', condCount=1;

function showTab(id,btn){
  document.querySelectorAll('.tc').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById(id).classList.add('active');btn.classList.add('active');
}

function pickPreset(id){
  document.querySelectorAll('#presets .card.ck').forEach(c=>c.classList.remove('sel'));
  document.getElementById('pc_'+id).classList.add('sel');
  document.getElementById('fPid').value=id;
  const p=P.find(r=>r.id===id);
  document.getElementById('ppT').textContent=lang==='es'?(p.name_es||p.name):p.name;
}
pickPreset('{{presets[0].id}}');

function pickType(t){
  document.getElementById('cType').value=t;
  document.getElementById('tSch').classList.toggle('sel',t==='schedule');
  document.getElementById('tCon').classList.toggle('sel',t==='condition');
  document.getElementById('cDet').style.display='block';
  document.getElementById('cCam').style.display='block';
  document.getElementById('cSub').style.display='block';
  document.getElementById('schF').style.display=t==='schedule'?'block':'none';
  document.getElementById('conF').style.display=t==='condition'?'block':'none';
}

function addCondition(){
  condCount++;
  const row=document.createElement('div');
  row.className='cond-row';
  row.id='cond_'+condCount;
  row.innerHTML=`
    <div class="fg"><label>${lang==='es'?'Metrica':'Metric'}</label>
      <select name="cond_metric">
        <option value="cpc">CPC</option><option value="cpm">CPM</option>
        <option value="cpa_checkout">CPA Checkout</option><option value="cpa_purchase">CPA Purchase</option>
        <option value="spend">${lang==='es'?'Gasto':'Spend'}</option>
        <option value="purchases">${lang==='es'?'Ventas':'Purchases'}</option>
        <option value="checkouts">Checkouts</option>
        <option value="days_running">${lang==='es'?'Dias Corriendo':'Days Running'}</option>
      </select></div>
    <div class="fg"><label>${lang==='es'?'Operador':'Operator'}</label>
      <select name="cond_op"><option value=">">&gt;</option><option value=">=">&ge;</option><option value="<">&lt;</option><option value="<=">&le;</option><option value="==">=</option></select></div>
    <div class="fg"><label>${lang==='es'?'Valor':'Value'}</label>
      <input type="number" step="0.01" name="cond_val" value="0"></div>
    <button type="button" class="cond-rm" onclick="rmCond('cond_${condCount}')">&#10005;</button>`;

  const andLabel=document.createElement('div');
  andLabel.className='and-label';andLabel.id='and_'+condCount;andLabel.textContent='AND';
  document.getElementById('condRows').appendChild(andLabel);
  document.getElementById('condRows').appendChild(row);
}

function rmCond(id){
  const num=id.split('_')[1];
  const andEl=document.getElementById('and_'+num);
  if(andEl)andEl.remove();
  document.getElementById(id).remove();
}

function loadC(selId,listId){
  const v=document.getElementById(selId).value;
  if(!v)return;
  const[bm,aid]=v.split('|');
  const el=document.getElementById(listId);
  el.innerHTML='<div style="text-align:center;padding:16px;color:#6b7280">Loading...</div>';
  fetch('/api/campaigns?bm='+bm+'&account_id='+aid)
    .then(r=>r.json()).then(data=>{
      if(!data.length){el.innerHTML='<div style="text-align:center;padding:16px;color:#6b7280">No campaigns</div>';return;}
      el.innerHTML=data.map(c=>'<div class="ci"><input type="checkbox" name="campaigns" value="'+c.id+'" checked style="accent-color:#3b82f6"><div><div class="cn">'+c.name+'</div><div class="cid">'+c.id+'</div></div></div>').join('');
    });
}

function togAll(id,on){document.querySelectorAll('#'+id+' input[type=checkbox]').forEach(c=>c.checked=!!on)}

function setLang(l){
  lang=l;
  document.getElementById('lEN').classList.toggle('active',l==='en');
  document.getElementById('lES').classList.toggle('active',l==='es');
  document.querySelectorAll('[data-'+l+']').forEach(el=>{const t=el.getAttribute('data-'+l);if(t)el.textContent=t;});
}

function toggleSelectAll(){const on=document.getElementById('selAll').checked;document.querySelectorAll('.rule-cb').forEach(c=>c.checked=on)}

function bulkAction(formId,action){
  const ids=Array.from(document.querySelectorAll('.rule-cb:checked')).map(c=>c.value);
  if(!ids.length){alert('Select at least one rule');return;}
  if(action==='delete'&&!confirm('Delete selected rules?'))return;
  const form=document.getElementById(formId);
  form.querySelector('input[name=rule_ids]').value=JSON.stringify(ids);
  form.submit();
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML,
        presets=PRESETS, presets_json=json.dumps(PRESETS),
        rules=load_rules(), logs=load_logs(), accounts=ALL_ACCOUNTS,
        now=datetime.now().strftime("%b %d, %Y %I:%M %p"))

@app.route("/api/campaigns")
def api_campaigns():
    return jsonify(get_campaigns(request.args.get("account_id"), get_token(request.args.get("bm"))))

@app.route("/create_rule", methods=["POST"])
def create_rule_route():
    source = request.form.get("source")
    account_val = request.form.get("account", "")
    campaign_ids = request.form.getlist("campaigns")
    custom_name = request.form.get("custom_name", "").strip()

    if not campaign_ids or not account_val:
        return redirect("/")

    bm, account_id, account_name = account_val.split("|")
    token = get_token(bm)

    campaign_names = {}
    for c in get_campaigns(account_id, token, "ACTIVE") + get_campaigns(account_id, token, "PAUSED"):
        if c["id"] in campaign_ids:
            campaign_names[c["id"]] = c["name"]

    if source == "preset":
        pid = request.form.get("preset_id")
        p = next((x for x in PRESETS if x["id"] == pid), None)
        if not p: return redirect("/")
        rule = {
            "id": f"{pid}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "name": custom_name or f"{p['name']} -- {account_name}",
            "type": p["type"], "action": p["action"],
            "bm": bm, "account_id": account_id, "account_name": account_name,
            "campaign_ids": campaign_ids, "campaign_names": campaign_names,
            "enabled": True, "is_custom": False, "created_at": datetime.now().isoformat(),
        }
        if p["type"] == "schedule":
            rule["hour"] = p["hour"]; rule["min"] = p["min"]
        else:
            rule["conditions"] = p["conditions"]
            rule["time_range"] = p.get("time_range", "last_3d")
            rule["check_freq"] = p.get("check_freq", "30min")

    elif source == "custom":
        ct = request.form.get("custom_type", "schedule")
        rule = {
            "id": f"custom_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "name": custom_name or f"Custom -- {account_name}",
            "type": ct, "bm": bm, "account_id": account_id, "account_name": account_name,
            "campaign_ids": campaign_ids, "campaign_names": campaign_names,
            "enabled": True, "is_custom": True, "created_at": datetime.now().isoformat(),
        }
        if ct == "schedule":
            rule["action"] = request.form.get("custom_action", "PAUSE")
            rule["hour"] = int(request.form.get("custom_hour", 23))
            rule["min"] = int(request.form.get("custom_minute", 0))
        else:
            rule["action"] = request.form.get("custom_action_condition", "PAUSE")
            rule["time_range"] = request.form.get("time_range", "last_3d")
            rule["check_freq"] = request.form.get("check_freq", "30min")

            metrics = request.form.getlist("cond_metric")
            ops = request.form.getlist("cond_op")
            vals = request.form.getlist("cond_val")
            rule["conditions"] = []
            for m, o, v in zip(metrics, ops, vals):
                try:
                    rule["conditions"].append({"metric": m, "op": o, "val": float(v)})
                except ValueError:
                    pass
    else:
        return redirect("/")

    meta_result = create_meta_rule(account_id, token, rule)
    if "id" in meta_result:
        rule["meta_rule_id"] = meta_result["id"]

    rules = load_rules()
    rules.append(rule)
    save_rules(rules)
    return redirect("/")

@app.route("/toggle_rule", methods=["POST"])
def toggle_rule():
    rid = request.form.get("rule_id")
    rules = load_rules()
    for r in rules:
        if r["id"] == rid:
            r["enabled"] = not r["enabled"]
            if r.get("meta_rule_id"):
                toggle_meta_rule(r["meta_rule_id"], get_token(r["bm"]), r["enabled"])
                append_log({"ts":datetime.now().strftime("%Y-%m-%d %H:%M"),"rule":r["name"],
                    "action":"ENABLED" if r["enabled"] else "PAUSED","ok":True,
                    "detail":"Status updated on Meta","campaign":r.get("account_name","")})
    save_rules(rules)
    return redirect("/")

@app.route("/delete_rule", methods=["POST"])
def delete_rule():
    rid = request.form.get("rule_id")
    rules = load_rules()
    for r in rules:
        if r["id"] == rid and r.get("meta_rule_id"):
            delete_meta_rule(r["meta_rule_id"], get_token(r["bm"]))
            append_log({"ts":datetime.now().strftime("%Y-%m-%d %H:%M"),"rule":r["name"],
                "action":"DELETED FROM META","ok":True,"detail":"Rule removed","campaign":r.get("account_name","")})
    save_rules([r for r in rules if r["id"] != rid])
    return redirect("/")

@app.route("/bulk_toggle", methods=["POST"])
def bulk_toggle():
    ids = json.loads(request.form.get("rule_ids", "[]"))
    action = request.form.get("action", "pause")
    rules = load_rules()
    for r in rules:
        if r["id"] in ids:
            r["enabled"] = action == "activate"
            if r.get("meta_rule_id"):
                toggle_meta_rule(r["meta_rule_id"], get_token(r["bm"]), r["enabled"])
    save_rules(rules)
    return redirect("/")

@app.route("/bulk_delete", methods=["POST"])
def bulk_delete():
    ids = json.loads(request.form.get("rule_ids", "[]"))
    rules = load_rules()
    for r in rules:
        if r["id"] in ids and r.get("meta_rule_id"):
            delete_meta_rule(r["meta_rule_id"], get_token(r["bm"]))
    save_rules([r for r in rules if r["id"] not in ids])
    return redirect("/")

@app.route("/clear_logs", methods=["POST"])
def clear_logs():
    with open(LOG_FILE, "w") as f: json.dump([], f)
    return redirect("/")

if __name__ == "__main__":
    print("\n  Rules Engine -> http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
