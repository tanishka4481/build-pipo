// ================================================================
// MAIN.CPP — The entry point. Ties all modules together.
// ================================================================
//
// This file is intentionally simple. All the real logic is in
// the modules. Main just calls them in the right order.
//
// FLOW:
//
//  setup() — runs once at power-on:
//    1. Start serial monitor (for debug messages)
//    2. Set up button
//    3. Set up OLED screen
//    4. Set up microphone
//    5. Set up speaker (SPIFFS)
//    6. Connect to Wi-Fi
//    7. Start a session on the backend
//    8. Show idle face — ready to play!
//
//  loop() — runs forever:
//    1. Keep OLED animation running (update every 125ms)
//    2. Watch for button press
//    3. When button pressed → record audio
//    4. When button released → send audio to backend
//    5. Backend replies → update face + play audio
//    6. Return to idle
//
// ================================================================

// ── Standard libraries ────────────────────────────────────────────
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ── Our modules (include in order) ───────────────────────────────
#include "1_config.h"
#include "2_wifi.h"
#include "3_microphone.h"
#include "4_oled.h"
#include "5_speaker.h"
#include "6_api.h"

// ── Global objects ────────────────────────────────────────────────
// These are declared here and used across modules via 'extern'
Adafruit_SSD1306 display(SCREEN_W, SCREEN_H, &Wire, -1);

// Audio buffer — holds one WAV recording
// Size: up to 4 seconds at 16kHz 16-bit mono = ~128KB + 44 header
uint8_t* audioBuffer = nullptr;
size_t   audioBytes  = 0;

// ================================================================
//  SETUP — runs once when the device powers on
// ================================================================
void setup() {
    // 1. Serial monitor — open this in PlatformIO to see debug logs
    Serial.begin(115200);
    delay(500);
    Serial.println("\n\n=== Speech Therapy Toy ===");
    Serial.println("[BOOT] Starting up...");

    // 2. Button — INPUT_PULLUP means it reads HIGH normally,
    //    LOW when pressed (because pressing connects it to GND)
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    Serial.println("[BOOT] Button ready on GPIO " + String(BUTTON_PIN));

    // 3. OLED screen — I2C on pins 8 and 9
    Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) {
        Serial.println("[BOOT] ERROR: OLED not found! Check SDA/SCL wiring.");
        // Flash built-in LED to signal error (if available)
        while (true) {
            delay(500);
        }
    }
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(WHITE);
    display.setCursor(20, 24);
    display.print("Starting up...");
    display.display();
    Serial.println("[BOOT] OLED screen OK");

    // 4. Microphone — I2S on pins 4, 5, 6
    mic_setup();

    // 5. Audio buffer — allocate from internal SRAM
    //    (no PSRAM on n8 variant, SRAM is 512KB which is enough)
    audioBuffer = (uint8_t*) malloc(AUDIO_BUF_SIZE);
    if (!audioBuffer) {
        Serial.println("[BOOT] ERROR: Not enough memory for audio buffer!");
        while (true) delay(500);
    }
    Serial.printf("[BOOT] Audio buffer: %d bytes in SRAM\n", AUDIO_BUF_SIZE);

    // 6. Speaker / SPIFFS
    speaker_setup();

    // 7. Wi-Fi
    display.clearDisplay();
    display.setCursor(20, 24);
    display.print("Connecting WiFi...");
    display.display();

    bool wifiOk = wifi_connect();
    if (!wifiOk) {
        oled_set_face(FACE_ERROR);
        Serial.println("[BOOT] No WiFi — check credentials in 1_config.h");
        // Don't halt — let the child still see the device
        // It just won't work until WiFi comes back
    }

    // 8. Start session on backend
    if (wifiOk) {
        display.clearDisplay();
        display.setCursor(10, 24);
        display.print("Saying hello...");
        display.display();

        bool sessionOk = api_start_session();
        if (!sessionOk) {
            Serial.println("[BOOT] Backend unreachable — check BACKEND_URL");
            Serial.println("[BOOT] If on Render free tier, first request may take 30s");
            oled_set_face(FACE_ERROR);
            delay(3000);
        }
    }

    // 9. Ready — show idle face
    oled_set_face(FACE_IDLE);
    Serial.println("[BOOT] Ready! Waiting for button press...");
    Serial.println("==========================================\n");
}

// ================================================================
//  LOOP — runs forever after setup()
// ================================================================
void loop() {

    // ── Keep the OLED animation running ──────────────────────────
    // oled_render() checks if 125ms have passed and updates the frame
    oled_render();

    // ── Watch for button press ────────────────────────────────────
    if (digitalRead(BUTTON_PIN) == LOW) {

        // Debounce: wait 30ms and check again to avoid false triggers
        // (buttons can briefly bounce when pressed)
        delay(30);
        if (digitalRead(BUTTON_PIN) != LOW) return;

        // ── Button confirmed pressed → start recording ────────────
        Serial.println("[LOOP] Button pressed — recording...");
        oled_set_face(FACE_LISTENING);

        // mic_record() blocks here until button released or 4s pass
        audioBytes = mic_record();

        if (audioBytes == 0) {
            // Recording was too short (< 150ms)
            Serial.println("[LOOP] Too short — ask child to hold longer");

            display.clearDisplay();
            display.setTextSize(1);
            display.setTextColor(WHITE);
            display.setCursor(0, 20);
            display.print("Hold the button");
            display.setCursor(0, 34);
            display.print("while you speak!");
            display.display();
            delay(2500);

            oled_set_face(FACE_IDLE);
            return;
        }

        // ── Audio captured → send to backend ─────────────────────
        oled_set_face(FACE_THINKING);  // show thinking face while waiting

        BackendResponse resp = api_submit_attempt(audioBuffer, audioBytes);

        if (!resp.success) {
            // Network or server error
            Serial.println("[LOOP] Backend error — showing retry message");
            display.clearDisplay();
            display.setTextSize(1);
            display.setTextColor(WHITE);
            display.setCursor(10, 20);
            display.print("Oops! Try again");
            display.setCursor(15, 34);
            display.print("in a moment...");
            display.display();
            delay(3000);
            oled_set_face(FACE_IDLE);
            return;
        }

        // ── Backend responded — update face + play audio ──────────
        oled_set_from_backend(resp.faceState, resp.advance);
        speaker_say(resp.ttsText);

        // Keep the result face showing for 4 seconds
        uint32_t showUntil = millis() + 4000;
        while (millis() < showUntil) {
            oled_render();  // keep animating while waiting
            delay(20);
        }

        // ── Back to idle ──────────────────────────────────────────
        oled_set_face(FACE_IDLE);
    }

    delay(20);  // small pause to prevent watchdog timer from triggering
}