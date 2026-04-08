// ================================================================
// MODULE 1 — CONFIG
// ================================================================
// This is the ONLY file you need to edit before flashing.
// Every setting lives here. Nothing else needs to change.
// ================================================================

#pragma once

// ── YOUR DETAILS ─────────────────────────────────────────────────

#define WIFI_SSID        "YOUR_WIFI_NAME"       // <-- change this
#define WIFI_PASSWORD    "YOUR_WIFI_PASSWORD"    // <-- change this
#define BACKEND_URL      "https://your-app.onrender.com"  // <-- change this
#define CHILD_ID         "child_001"             // <-- change this per child

// ── PIN NUMBERS ───────────────────────────────────────────────────
//
//  What is a pin? It's the numbered hole on your ESP32-S3 board.
//  A wire connects from the component to that pin number.
//
//  INMP441 Microphone (I2S digital mic — 3 wires for audio data)
#define MIC_WS_PIN    4    // WS  = Word Select (also called LRCLK)
#define MIC_SCK_PIN   5    // SCK = Clock
#define MIC_SD_PIN    6    // SD  = Data (audio signal)

//  SSD1306 OLED Screen (I2C — only 2 wires needed)
#define OLED_SDA_PIN  8    // SDA = Data
#define OLED_SCL_PIN  9    // SCL = Clock
#define OLED_I2C_ADDR 0x3C // Default I2C address for SSD1306

//  Press-to-Speak Button (1 wire — other leg goes to GND)
#define BUTTON_PIN    0    // GPIO 0 — has internal pull-up resistor built in

//  Speaker output (PWM audio output on ESP32-S3)
#define DAC_PIN       17   // GPIO 17 → wire to PAM8403 audio input

// ── SCREEN SIZE ───────────────────────────────────────────────────
#define SCREEN_W  128
#define SCREEN_H   64

// ── AUDIO SETTINGS ────────────────────────────────────────────────
//
//  These must match what the backend expects.
//  Backend (stage1_preprocess.py) uses SR_TARGET = 16000
//
#define SAMPLE_RATE    16000   // 16,000 samples per second
#define MAX_REC_MS     4000    // Stop recording after 4 seconds max
#define MIN_REC_MS      150    // Ignore recordings shorter than 0.15s

//  How big a buffer do we need?
//  16000 samples/sec × 2 bytes/sample × 4 sec = 128,000 bytes
//  + 44 bytes for WAV file header
#define AUDIO_BUF_SIZE  (SAMPLE_RATE * 2 * (MAX_REC_MS / 1000) + 44)

// ── BACKEND SESSION ───────────────────────────────────────────────
#define START_LEVEL      "isolation"   // Starting difficulty level
#define TARGET_PHONEME   "s"           // The sound being practiced