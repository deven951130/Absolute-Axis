/*
 * Absolute Axis - ESP32 電源控制（Cloudflare Worker 版）
 *
 * ESP32 每 2 秒主動 HTTPS 連到 Worker：
 *   - 回報 主機開關狀態 / 溫濕度 / WiFi 訊號 / 已執行的指令 ID
 *   - 取回待執行指令，執行電源鍵動作
 * 不需要開 port，也不需要 Tunnel；ESP32 只往外連。
 * 另外開啟 ArduinoOTA (port 3232)，同區網的機器可用網路燒錄。
 *
 * 需要的函式庫：ESP32 Arduino core（內建 WiFi / WiFiClientSecure / HTTPClient）、
 *               "DHT sensor library" by Adafruit（+ Adafruit Unified Sensor）
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoOTA.h>
#include <DHT.h>
#include "secrets.h"   // 由 secrets.example.h 複製

// ===== 硬體設定 =====
const int  POWER_PIN          = 4;    // 與原 power.ino 相同 (RELAY_PIN)
const bool POWER_ACTIVE_HIGH  = true;   // 繼電器若低電位觸發改成 false
const int  PC_LED_PIN         = -1;     // 目前沒有接電源 LED 偵測；接了再改腳位
const bool PC_LED_ACTIVE_HIGH = true;
const int  DHT_PIN            = 5;    // 與原 power.ino 相同
#define    DHT_TYPE DHT11               // 與原 power.ino 相同

const unsigned long SHORT_PRESS_MS  = 500;
const unsigned long LONG_PRESS_MS   = 5000;
const unsigned long SYNC_INTERVAL_MS = 2000;
const unsigned long DHT_INTERVAL_MS  = 3000;

DHT dht(DHT_PIN, DHT_TYPE);
WiFiClientSecure secureClient;

long          lastExecutedId = 0;   // 已執行過的最大指令 ID，防止重複執行
unsigned long lastSyncMs     = 0;
unsigned long lastDhtMs      = 0;
float         lastTemp       = NAN;
float         lastHumid      = NAN;

void setPowerPin(bool active) {
  digitalWrite(POWER_PIN, (active == POWER_ACTIVE_HIGH) ? HIGH : LOW);
}

// 回傳 1=開機, 0=關機, -1=未接偵測
int readPcState() {
  if (PC_LED_PIN < 0) return -1;
  bool level = digitalRead(PC_LED_PIN) == HIGH;
  return (level == PC_LED_ACTIVE_HIGH) ? 1 : 0;
}

// 按住電源鍵（會阻塞 ms 毫秒，長按 5 秒期間 ESP32 不做其他事）
void pressPower(unsigned long ms) {
  Serial.printf("[POWER] press %lu ms\n", ms);
  setPowerPin(true);
  delay(ms);
  setPowerPin(false);
}

String buildReport(int pc, long ackId) {
  String j = "{";
  j += "\"pc_on\":" + String(pc < 0 ? "null" : (pc ? "true" : "false"));
  j += ",\"temp\":" + (isnan(lastTemp) ? String("null") : String(lastTemp, 1));
  j += ",\"humid\":" + (isnan(lastHumid) ? String("null") : String(lastHumid, 1));
  j += ",\"rssi\":" + String(WiFi.RSSI());
  j += ",\"ack\":" + String(ackId);
  j += "}";
  return j;
}

void syncWithServer() {
  HTTPClient http;
  String url = String(SERVER_URL) + "/device/sync";
  if (!http.begin(secureClient, url)) {
    Serial.println("[SYNC] http.begin failed");
    return;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + DEVICE_TOKEN);
  http.setTimeout(8000);

  int code = http.POST(buildReport(readPcState(), lastExecutedId));
  if (code == 200) {
    String body = http.getString();
    // 回應格式：{"cmd":{"id":N,"action":"press|force"}} 或 {"cmd":null}
    int idPos = body.indexOf("\"id\":");
    if (idPos >= 0) {
      long id = body.substring(idPos + 5).toInt();
      if (id > lastExecutedId) {
        if (body.indexOf("\"action\":\"press\"") >= 0) {
          pressPower(SHORT_PRESS_MS);
        } else if (body.indexOf("\"action\":\"force\"") >= 0) {
          pressPower(LONG_PRESS_MS);
        }
        lastExecutedId = id;   // 下次 sync 會把這個 ID 回報為 ack
      }
    }
  } else {
    Serial.printf("[SYNC] HTTP %d\n", code);
  }
  http.end();
}

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
  setPowerPin(false);                  // 開機時確保不會誤觸電源鍵
  if (PC_LED_PIN >= 0) pinMode(PC_LED_PIN, INPUT);

  dht.begin();
  connectWiFi();

  // TODO: 驗證 Cloudflare 憑證鏈後改用 setCACert() 做憑證固定；目前暫時不驗證憑證
  secureClient.setInsecure();

  // ArduinoOTA：讓同區網的機器可以用網路燒錄（port 3232）
  ArduinoOTA.setHostname(OTA_HOSTNAME);
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() {
    setPowerPin(false);                // 燒錄期間確保電源鍵是放開的
    Serial.println("[OTA] Start");
  });
  ArduinoOTA.onEnd([]() { Serial.println("[OTA] End"); });
  ArduinoOTA.onError([](ota_error_t err) { Serial.printf("[OTA] Error %u\n", err); });
  ArduinoOTA.begin();
}

void loop() {
  ArduinoOTA.handle();
  unsigned long now = millis();

  // WiFi 斷線重連
  static unsigned long lastWifiCheck = 0;
  if (WiFi.status() != WL_CONNECTED && now - lastWifiCheck > 10000) {
    lastWifiCheck = now;
    Serial.println("[WiFi] Reconnecting...");
    WiFi.reconnect();
  }

  if (now - lastDhtMs >= DHT_INTERVAL_MS) {
    lastDhtMs = now;
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) lastTemp = t;
    if (!isnan(h)) lastHumid = h;
  }

  if (WiFi.status() == WL_CONNECTED && now - lastSyncMs >= SYNC_INTERVAL_MS) {
    lastSyncMs = now;
    syncWithServer();
  }
}
