// ================================================================
// MODULE 6 — BACKEND API
// ================================================================
// Handles all communication with your FastAPI server on Render.
//
// Two API calls:
//
//   api_start_session()
//     Called once when the device boots up.
//     Tells the backend: "a new practice session is starting"
//     Backend creates a session record and gives us a session_id.
//     We store session_id and use it in every attempt call.
//
//   api_submit_attempt(wavBuffer, wavSize)
//     Called after every recording.
//     Sends the WAV audio (as base64 text) to the backend.
//     Backend runs: Stage1 (preprocess) → Stage2 (features) →
//                   Stage3 (score+decision) → returns JSON
//     We read the JSON and return what to show + say.
//
// What is base64?
//   Audio is binary data (bytes). HTTP forms work with text.
//   Base64 converts binary → text so we can send it in a form.
//   Example: byte 0xFF becomes "Yw==" in base64.
// ================================================================

#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "1_config.h"
#include "2_wifi.h"

// ── Session state (global) ────────────────────────────────────────
String g_sessionId    = "";
int    g_attemptNum   = 0;
String g_currentLevel = START_LEVEL;

// ── Return struct: what the backend told us to do ─────────────────
struct BackendResponse {
    bool   success;       // false = HTTP error, ignore the rest
    String faceState;     // e.g. "big_happy", "curious_tilt"
    String ttsText;       // e.g. "Wow, you're amazing at this!"
    bool   advance;       // true = child levelled up
    bool   dropBack;      // true = child dropped a level
    String newLevel;      // e.g. "syllable"
    float  score;         // 0.0 to 1.0
};

// ── Base64 encoder ────────────────────────────────────────────────
// Converts binary audio bytes → text string for HTTP transmission
// ESP32 Arduino has base64 built in as base64::encode()
#include <base64.h>

// ── POST /session/start ───────────────────────────────────────────
bool api_start_session() {
    wifi_ensure();

    HTTPClient http;
    http.begin(String(BACKEND_URL) + "/session/start");
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(10000);

    // Build JSON body
    // {"child_id": "child_001", "level": "isolation", "target_phoneme": "s"}
    String body = "{\"child_id\":\"" + String(CHILD_ID) +
                  "\",\"level\":\"" + String(START_LEVEL) +
                  "\",\"target_phoneme\":\"" + String(TARGET_PHONEME) + "\"}";

    Serial.println("[API] Starting session...");
    int code = http.POST(body);

    if (code == 200) {
        JsonDocument doc;
        deserializeJson(doc, http.getString());
        g_sessionId = doc["session_id"].as<String>();
        Serial.printf("[API] Session started. ID: %s\n", g_sessionId.c_str());
        http.end();
        return true;
    }

    Serial.printf("[API] Session start failed. HTTP %d\n", code);
    http.end();
    return false;
}

// ── POST /attempt ─────────────────────────────────────────────────
//
// This is the main call. Sends audio → gets back what to show/say.
//
// How the form is built:
//   The backend /attempt endpoint expects multipart/form-data.
//   That's the same format as a file upload form on a website.
//   We manually build the form fields as text with a boundary marker.
//
BackendResponse api_submit_attempt(uint8_t* wavBuf, size_t wavLen) {
    BackendResponse result;
    result.success = false;

    wifi_ensure();

    // Step 1: Encode WAV bytes → base64 string
    Serial.println("[API] Encoding audio to base64...");
    String b64 = base64::encode(wavBuf, wavLen);
    Serial.printf("[API] Audio size: %d bytes → base64: %d chars\n",
                  (int)wavLen, b64.length());

    // Step 2: Build multipart form-data body
    // A "boundary" is just a unique string that separates form fields
    String boundary = "ESP32Boundary1234";
    String body = "";

    // Helper: add a text field to the form
    auto addField = [&](const String& name, const String& value) {
        body += "--" + boundary + "\r\n";
        body += "Content-Disposition: form-data; name=\"" + name + "\"\r\n\r\n";
        body += value + "\r\n";
    };

    addField("session_id",     g_sessionId);
    addField("child_id",       CHILD_ID);
    addField("attempt_number", String(++g_attemptNum));
    addField("current_level",  g_currentLevel);
    addField("target_phoneme", TARGET_PHONEME);
    addField("target_word",    "");
    addField("audio_b64",      b64);       // the actual audio data
    body += "--" + boundary + "--\r\n";    // end of form

    // Step 3: Send HTTP POST
    HTTPClient http;
    http.begin(String(BACKEND_URL) + "/attempt");
    http.addHeader("Content-Type",
                   "multipart/form-data; boundary=" + boundary);
    http.setTimeout(20000);  // 20 seconds — Render cold starts can be slow

    Serial.println("[API] Sending attempt to backend...");
    int code = http.POST(body);
    Serial.printf("[API] HTTP response: %d\n", code);

    if (code != 200) {
        Serial.printf("[API] Error. Body: %s\n", http.getString().c_str());
        http.end();
        return result;
    }

    // Step 4: Parse JSON response
    String responseStr = http.getString();
    Serial.println("[API] Response: " + responseStr);

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, responseStr);
    if (err) {
        Serial.println("[API] JSON parse error");
        http.end();
        return result;
    }

    // Step 5: Fill result struct
    result.success    = true;
    result.faceState  = doc["face_state"].as<String>();
    result.ttsText    = doc["tts_text"].as<String>();
    result.advance    = doc["advance"].as<bool>();
    result.dropBack   = doc["drop_back"].as<bool>();
    result.newLevel   = doc["new_level"].as<String>();
    result.score      = doc["score"].as<float>();

    // Update level tracking
    g_currentLevel = result.newLevel;

    Serial.printf("[API] Score: %.2f | Level: %s | Advance: %s\n",
                  result.score,
                  result.newLevel.c_str(),
                  result.advance ? "YES" : "no");

    http.end();
    return result;
}