// Absolute Axis - 伺服器電源控制 Cloudflare Worker
//
// 路由：
//   GET  /               控制網頁（由 Cloudflare Access 保護）
//   GET  /api/status     目前狀態（由 Cloudflare Access 保護）
//   POST /api/power?action=press|force   排入電源指令（由 Cloudflare Access 保護）
//   POST /device/sync    ESP32 定時回報狀態、取得指令（Bearer DEVICE_TOKEN，Access 需對此路徑 Bypass）
//
// 狀態與指令佇列存在 Durable Object (PowerState)，避免 KV 最終一致性造成延遲。

import { DurableObject } from "cloudflare:workers";

const PENDING_TTL_MS = 60_000; // 超過 60 秒未被執行的指令自動作廢（防止 ESP32 重開機後誤按）
const ONLINE_WINDOW_MS = 15_000;

const HTML = `<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Absolute Axis 電源控制</title>
<style>
body{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;margin:0;display:flex;justify-content:center}
.card{max-width:420px;width:100%;margin:32px 16px;background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px}
h1{font-size:20px;margin:0 0 16px}
.row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #21262d}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;background:#8b949e}
.on{background:#2ecc71;box-shadow:0 0 8px #2ecc71}.off{background:#da3633}
button{width:100%;padding:14px;margin-top:14px;font-size:16px;border:0;border-radius:8px;cursor:pointer;color:#fff}
#press{background:#238636}#force{background:#da3633}button:disabled{opacity:.5;cursor:wait}
#msg{margin-top:12px;font-size:14px;color:#8b949e;min-height:1em}
</style></head><body><div class="card">
<h1>⚡ Absolute Axis 伺服器電源</h1>
<div class="row"><span>ESP32 狀態</span><span id="online">--</span></div>
<div class="row"><span>主機狀態</span><span><span id="dot" class="dot"></span><span id="pc">--</span></span></div>
<div class="row"><span>溫度</span><span id="t">--</span></div>
<div class="row"><span>濕度</span><span id="h">--</span></div>
<div class="row"><span>WiFi 訊號</span><span id="rssi">--</span></div>
<div class="row"><span>最後指令</span><span id="last">--</span></div>
<button id="press" onclick="act('press','確定要按下電源鍵（開機 / 正常關機）？')">電源鍵（短按）</button>
<button id="force" onclick="act('force','確定要強制關機？未存檔資料會遺失！')">強制關機（長按 5 秒）</button>
<div id="msg"></div>
</div><script>
function fmt(v,suffix){return v===null||v===undefined?'--':v+suffix;}
async function refresh(){
  try{
    const r=await fetch('/api/status',{cache:'no-store'});
    const d=await r.json();
    document.getElementById('online').textContent=d.device_online?'在線（'+d.last_seen_s_ago+' 秒前）':'離線';
    const pc=document.getElementById('pc'),dot=document.getElementById('dot');
    if(d.pc_on===null){pc.textContent='未接偵測';dot.className='dot';}
    else{pc.textContent=d.pc_on?'運行中':'已關機';dot.className='dot '+(d.pc_on?'on':'off');}
    document.getElementById('t').textContent=d.temp===null?'--':d.temp.toFixed(1)+' °C';
    document.getElementById('h').textContent=d.humid===null?'--':d.humid.toFixed(0)+' %';
    document.getElementById('rssi').textContent=fmt(d.rssi,' dBm');
    document.getElementById('last').textContent=d.last_action?d.last_action+'（'+d.last_action_ago_s+' 秒前）':'--';
    ['press','force'].forEach(function(id){document.getElementById(id).disabled=d.pending;});
  }catch(e){document.getElementById('msg').textContent='無法取得狀態';}
}
async function act(a,q){
  if(!confirm(q))return;
  const r=await fetch('/api/power?action='+a,{method:'POST'});
  const msg=document.getElementById('msg');
  if(r.ok)msg.textContent='已排入指令，ESP32 約 2~3 秒內執行';
  else if(r.status===409)msg.textContent='上一個指令還在處理中';
  else msg.textContent='失敗 ('+r.status+')';
  refresh();
}
refresh();setInterval(refresh,2000);
</script></body></html>`;

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });

export class PowerState extends DurableObject {
  async load() {
    return (
      (await this.ctx.storage.get("s")) ?? {
        pc_on: null,
        temp: null,
        humid: null,
        rssi: null,
        lastSeen: 0,
        pending: null, // { id, action, at }
        seq: 0,
        lastAction: null,
        lastActionAt: 0,
      }
    );
  }

  async save(s) {
    await this.ctx.storage.put("s", s);
  }

  // 過期的待執行指令直接作廢
  expirePending(s) {
    if (s.pending && Date.now() - s.pending.at > PENDING_TTL_MS) s.pending = null;
  }

  async status() {
    const s = await this.load();
    this.expirePending(s);
    const now = Date.now();
    return {
      pc_on: s.pc_on,
      temp: s.temp,
      humid: s.humid,
      rssi: s.rssi,
      pending: s.pending !== null,
      device_online: s.lastSeen > 0 && now - s.lastSeen < ONLINE_WINDOW_MS,
      last_seen_s_ago: s.lastSeen ? Math.floor((now - s.lastSeen) / 1000) : null,
      last_action: s.lastAction,
      last_action_ago_s: s.lastActionAt ? Math.floor((now - s.lastActionAt) / 1000) : null,
    };
  }

  async queue(action) {
    const s = await this.load();
    this.expirePending(s);
    if (s.pending) return { error: "busy" };
    s.seq += 1;
    const now = Date.now();
    s.pending = { id: s.seq, action, at: now };
    s.lastAction = action;
    s.lastActionAt = now;
    await this.save(s);
    return { ok: true, id: s.seq };
  }

  // ESP32 每 2 秒呼叫一次：回報狀態、確認已執行的指令，並取回待執行指令
  async sync(report) {
    const s = await this.load();
    const now = Date.now();
    s.lastSeen = now;
    if (report.pc_on === true || report.pc_on === false || report.pc_on === null) s.pc_on = report.pc_on;
    s.temp = typeof report.temp === "number" ? report.temp : null;
    s.humid = typeof report.humid === "number" ? report.humid : null;
    s.rssi = typeof report.rssi === "number" ? report.rssi : null;

    this.expirePending(s);
    if (s.pending && typeof report.ack === "number" && report.ack >= s.pending.id) {
      s.pending = null; // 裝置已執行
    }
    await this.save(s);
    return { cmd: s.pending ? { id: s.pending.id, action: s.pending.action } : null };
  }
}

function deviceAuthorized(request, env) {
  const expected = `Bearer ${env.DEVICE_TOKEN}`;
  return env.DEVICE_TOKEN && request.headers.get("authorization") === expected;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const stub = env.POWER.get(env.POWER.idFromName("main"));

    if (request.method === "GET" && url.pathname === "/") {
      return new Response(HTML, {
        headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
      });
    }

    if (request.method === "GET" && url.pathname === "/api/status") {
      return json(await stub.status());
    }

    if (request.method === "POST" && url.pathname === "/api/power") {
      const action = url.searchParams.get("action");
      if (action !== "press" && action !== "force") {
        return json({ error: "action must be press or force" }, 400);
      }
      const result = await stub.queue(action);
      return result.error ? json(result, 409) : json(result);
    }

    if (request.method === "POST" && url.pathname === "/device/sync") {
      if (!deviceAuthorized(request, env)) return json({ error: "unauthorized" }, 401);
      let report;
      try {
        report = await request.json();
      } catch {
        return json({ error: "invalid json" }, 400);
      }
      return json(await stub.sync(report));
    }

    return new Response("Not found", { status: 404 });
  },
};
