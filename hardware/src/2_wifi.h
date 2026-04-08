// ================================================================
// MODULE 2 — WIFI
// ================================================================
// Handles connecting to Wi-Fi and staying connected.
//
// What happens:
//   1. Call wifi_connect() once at startup
//   2. Call wifi_ensure() before every API call — it
//      silently reconnects if the connection dropped
// ================================================================

#pragma once
#include <WiFi.h>
#include "1_config.h"

// ── Connect to Wi-Fi ─────────────────────────────────────────────
//
// Tries for 15 seconds. If it fails, returns false.
// The device will still work but won't be able to talk to backend.
//
bool wifi_connect() {
    Serial.printf("[WiFi] Connecting to: %s\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int tries = 0;
    while (WiFi.status() != WL_CONNECTED && tries < 30) {
        delay(500);
        Serial.print(".");
        tries++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WiFi] Connected! IP: %s\n",
                      WiFi.localIP().toString().c_str());
        return true;
    }

    Serial.println("\n[WiFi] Failed to connect.");
    return false;
}

// ── Make sure Wi-Fi is still connected ───────────────────────────
//
// Call this before any HTTP request.
// If connection dropped (e.g. walked out of range), it reconnects.
//
void wifi_ensure() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[WiFi] Dropped — reconnecting...");
        WiFi.disconnect();
        delay(200);
        wifi_connect();
    }
}