/*
 * Absolute Axis - ESP32 伺服器電源控制（本地網頁版，不依賴 Blynk）
 *
 * 功能：
 *   - ESP32 連上 WiFi 後自己開一個 HTTP 網頁 (http://<ESP32 IP>/ 或 http://axis-power.local/)
 *   - 網頁按鈕：短按電源（開機 / 正常關機）、長按 5 秒（強制關機）
 *   - 顯示主機狀態（若有接電源 LED 偵測腳）與 DHT 溫濕度
 *   - JSON API：GET /api/status、POST /api/power?action=press|force
 *   - 全部頁面與 API 皆需 HTTP Basic Auth 帳密
 *
 * 接線（預設，可於下方修改）：
 *   POWER_PIN (GPIO26) -> 光耦 / 繼電器，輸出端並聯在主機板 PWR_SW 兩腳
 *   PC_LED_PIN (GPIO34) -> 主機板 PWR_LED+（經分壓/光耦）用來判斷是否開機；不接請設 -1
 *   DHT_PIN   (GPIO4)  -> DHT22 / DHT11 資料腳
 *
 * 需要的函式庫：ESP32 Arduino core（內建 WiFi / WebServer / ESPmDNS）、
 *               "DHT sensor library" by Adafruit（+ Adafruit Unified Sensor）
 */

#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <DHT.h>
#include "secrets.h"   // 由 secrets.example.h 複製

// ===== 硬體設定 =====
const int  POWER_PIN          = 26;
const bool POWER_ACTIVE_HIGH  = true;   // 繼電器模組若是低電位觸發改成 false
const int  PC_LED_PIN         = 34;     // 不接電源 LED 偵測請設 -1
const bool PC_LED_ACTIVE_HIGH = true;
const int  DHT_PIN            = 4;
#define    DHT_TYPE DHT22               // DHT11 請改 DHT11

const unsigned long SHORT_PRESS_MS = 500;
const unsigned long LONG_PRESS_MS  = 5000;
const char* MDNS_NAME = "axis-power";   // http://axis-power.local/

WebServer server(80);
DHT dht(DHT_PIN, DHT_TYPE);

// 非阻塞按壓狀態
bool          pressing      = false;
unsigned long pressStartMs  = 0;
unsigned long pressDuration = 0;
String        lastAction    = "none";
unsigned long lastActionMs  = 0;

// 溫濕度快取
float         lastTemp  = NAN;
float         lastHumid = NAN;
unsigned long lastDhtMs = 0;

// ===== 網頁 =====
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8">
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
<div class="row"><span>主機狀態</span><span><span id="dot" class="dot"></span><span id="pc">--</span></span></div>
<div class="row"><span>溫度</span><span id="t">--</span></div>
<div class="row"><span>濕度</span><span id="h">--</span></div>
<div class="row"><span>ESP32 訊號</span><span id="rssi">--</span></div>
<button id="press" onclick="act('press','確定要按下電源鍵（開機 / 正常關機）？')">電源鍵（短按）</button>
<button id="force" onclick="act('force','確定要強制關機？未存檔資料會遺失！')">強制關機（長按 5 秒）</button>
<div id="msg"></div>
</div><script>
async function refresh(){
  try{
    const r=await fetch('/api/status');const d=await r.json();
    const pc=document.getElementById('pc'),dot=document.getElementById('dot');
    if(d.pc_on===null){pc.textContent='未接偵測';dot.className='dot';}
    else{pc.textContent=d.pc_on?'運行中':'已關機';dot.className='dot '+(d.pc_on?'on':'off');}
    document.getElementById('t').textContent=d.temp===null?'--':d.temp.toFixed(1)+' °C';
    document.getElementById('h').textContent=d.humid===null?'--':d.humid.toFixed(0)+' %';
    document.getElementById('rssi').textContent=d.rssi+' dBm';
    ['press','force'].forEach(id=>document.getElementById(id).disabled=d.pressing);
  }catch(e){document.getElementById('msg').textContent='無法連線 ESP32';}
}
async function act(a,q){
  if(!confirm(q))return;
  const r=await fetch('/api/power?action='+a,{method:'POST'});
  document.getElementById('msg').textContent=r.ok?'已送出指令：'+a:'失敗 ('+r.status+')';
  refresh();
}
refresh();setInterval(refresh,3000);
</script></body></html>
)rawliteral";

// ===== 工具函式 =====
void setPowerPin(bool active) {
  digitalWrite(POWER_PIN, (active == POWER_ACTIVE_HIGH) ? HIGH : LOW);
}

bool checkAuth() {
  if (!server.authenticate(WEB_USER, WEB_PASSWORD)) {
    server.requestAuthentication(BASIC_AUTH, "Absolute Axis Power");
    return false;
  }
  return true;
}

// 回傳 1=開機, 0=關機, -1=未接偵測
int readPcState() {
  if (PC_LED_PIN < 0) return -1;
  bool level = digitalRead(PC_LED_PIN) == HIGH;
  return (level == PC_LED_ACTIVE_HIGH) ? 1 : 0;
}

String jsonFloatOrNull(float v, int decimals) {
  return isnan(v) ? String("null") : String(v, decimals);
}

// ===== HTTP Handlers =====
void handleRoot() {
  if (!checkAuth()) return;
  server.send_P(200, "text/html; charset=utf-8", INDEX_HTML);
}

void handleStatus() {
  if (!checkAuth()) return;
  int pc = readPcState();
  String json = "{";
  json += "\"pc_on\":" + String(pc < 0 ? "null" : (pc ? "true" : "false"));
  json += ",\"temp\":" + jsonFloatOrNull(lastTemp, 1);
  json += ",\"humid\":" + jsonFloatOrNull(lastHumid, 1);
  json += ",\"pressing\":" + String(pressing ? "true" : "false");
  json += ",\"last_action\":\"" + lastAction + "\"";
  json += ",\"last_action_ago_s\":" + String(lastActionMs ? (millis() - lastActionMs) / 1000 : 0);
  json += ",\"rssi\":" + String(WiFi.RSSI());
  json += ",\"uptime_s\":" + String(millis() / 1000);
  json += "}";
  server.send(200, "application/json", json);
}

void handlePower() {
  if (!checkAuth()) return;
  if (pressing) {
    server.send(409, "application/json", "{\"error\":\"busy\"}");
    return;
  }
  String action = server.arg("action");
  if (action == "press")      pressDuration = SHORT_PRESS_MS;
  else if (action == "force") pressDuration = LONG_PRESS_MS;
  else {
    server.send(400, "application/json", "{\"error\":\"action must be press or force\"}");
    return;
  }
  pressing     = true;
  pressStartMs = millis();
  lastAction   = action;
  lastActionMs = pressStartMs;
  setPowerPin(true);
  Serial.printf("[POWER] %s (%lu ms)\n", action.c_str(), pressDuration);
  server.send(200, "application/json", "{\"ok\":true,\"action\":\"" + action + "\"}");
}

// ===== 主程式 =====
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Connecting");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WiFi] IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("[WiFi] 連線失敗，將在 loop 中持續重試");
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(POWER_PIN, OUTPUT);
  setPowerPin(false);                 // 開機時確保不會誤觸電源鍵
  if (PC_LED_PIN >= 0) pinMode(PC_LED_PIN, INPUT);

  dht.begin();
  connectWiFi();

  if (MDNS.begin(MDNS_NAME)) {
    MDNS.addService("http", "tcp", 80);
    Serial.printf("[mDNS] http://%s.local/\n", MDNS_NAME);
  }

  server.on("/", HTTP_GET, handleRoot);
  server.on("/api/status", HTTP_GET, handleStatus);
  server.on("/api/power", HTTP_POST, handlePower);
  server.onNotFound([]() { server.send(404, "text/plain", "Not found"); });
  server.begin();
  Serial.println("[HTTP] Server started");
}

void loop() {
  server.handleClient();

  // 非阻塞放開電源鍵
  if (pressing && millis() - pressStartMs >= pressDuration) {
    setPowerPin(false);
    pressing = false;
    Serial.println("[POWER] released");
  }

  // 每 3 秒讀一次 DHT
  if (millis() - lastDhtMs >= 3000) {
    lastDhtMs = millis();
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) lastTemp = t;
    if (!isnan(h)) lastHumid = h;
  }

  // WiFi 斷線重連（每 10 秒嘗試一次）
  static unsigned long lastWifiCheck = 0;
  if (WiFi.status() != WL_CONNECTED && millis() - lastWifiCheck > 10000) {
    lastWifiCheck = millis();
    Serial.println("[WiFi] Reconnecting...");
    WiFi.reconnect();
  }
}
