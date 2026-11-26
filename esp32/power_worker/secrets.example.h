// 複製此檔為 secrets.h 並填入真實值（secrets.h 已被 .gitignore 排除，不會進 Git）
#pragma once

#define WIFI_SSID     "你的WiFi名稱"
#define WIFI_PASSWORD "你的WiFi密碼"

// Worker 的公開網址（不要結尾斜線）
#define SERVER_URL    "https://power.example.com"

// 裝置金鑰，必須與 Worker 的 DEVICE_TOKEN secret 相同
// 產生方式：openssl rand -hex 32
#define DEVICE_TOKEN  "replace-with-long-random-token"

// ArduinoOTA 網路燒錄（同區網用），密碼請改掉
#define OTA_HOSTNAME  "Axis-ESP32-Power"
#define OTA_PASSWORD  "change-me-ota"
