// ================================================================
// MODULE 5 — SPEAKER (TTS PLAYBACK)
// ================================================================
// Plays audio responses through the PAM8403 amplifier + speaker.
//
// How it works:
//   - The backend returns a tts_text string (e.g. "Great job!")
//   - We match that text to a pre-recorded WAV file stored in
//     the ESP32-S3's internal flash (SPIFFS filesystem)
//   - We play that WAV file through GPIO17 (PWM) → PAM8403 → speaker
//
// IMPORTANT — You need to prepare audio files:
//   Step 1: Generate WAV files for each phrase (see list below)
//           Use ElevenLabs, Google TTS, or record your own voice
//           Settings: 8kHz sample rate, mono, 16-bit PCM
//   Step 2: Name them tts_01.wav, tts_02.wav, etc.
//   Step 3: In PlatformIO, create a "data" folder in your project
//           and put all WAV files there
//   Step 4: In PlatformIO, run: Tasks → Upload Filesystem Image
//           This uploads the files to the ESP32-S3's flash memory
//
// DAC connection:
//   GPIO 17 → PAM8403 "Left IN" pin
//   PAM8403 OUT+ → Speaker +
//   PAM8403 OUT- → Speaker -
//   PAM8403 VCC  → 5V
//   PAM8403 GND  → GND
// ================================================================

#pragma once
#include <Arduino.h>
#include <SPIFFS.h>
#include "1_config.h"

#define SPEAKER_PWM_CHANNEL    0
#define SPEAKER_PWM_FREQ       20000
#define SPEAKER_PWM_RESOLUTION 8

// ── TTS phrase lookup table ───────────────────────────────────────
// Maps each backend phrase → WAV filename in SPIFFS
// These phrases come from stage3_feedback.py in the _TTS dictionary

struct TtsEntry {
    const char* text;
    const char* file;
};

const TtsEntry TTS_TABLE[] = {
    // ── No attempt ────────────────────────────────────────────────
    {"Hmm, I didn't quite hear that. Can you try again?",     "/tts_01.wav"},
    {"I'm listening... can you help me?",                     "/tts_02.wav"},
    {"Oops, I missed it! One more time?",                     "/tts_03.wav"},

    // ── Praise (correct) ──────────────────────────────────────────
    {"Yes! You're so good at teaching me!",                   "/tts_04.wav"},
    {"That's it! I felt it — ssss — just like that!",         "/tts_05.wav"},
    {"Wow, you're amazing at this!",                          "/tts_06.wav"},
    {"Perfect! I almost got it — do it one more time?",       "/tts_07.wav"},
    {"I heard it! You're a great teacher!",                   "/tts_08.wav"},

    // ── Praise + advance (level up) ───────────────────────────────
    {"You've taught me so well, let's try something harder!", "/tts_09.wav"},
    {"You're SO good at this — ready for the next challenge?","/tts_10.wav"},
    {"Level up! You're the best teacher I've ever had!",      "/tts_11.wav"},

    // ── Corrective hints ──────────────────────────────────────────
    {"Ooh so close! Try pushing more air through your front teeth — ssssss.", "/tts_12.wav"},
    {"Almost! Make the sound sharper — like a hiss. Teeth together, ssss!",  "/tts_13.wav"},
    {"So close! Let the air stream out steadily — like a slow hiss.",        "/tts_14.wav"},
    {"Great sound! Can you hold it a little longer? Sssssssss — like that!", "/tts_15.wav"},

    // ── Model sound (wrong phoneme) ───────────────────────────────
    {"Hmm I got confused! Let me show you — ssssss. Can you copy that?",     "/tts_16.wav"},
    {"Hmm, I'm confused. Listen to how I do it — ssssss. Now you try!",      "/tts_17.wav"},
};

const int TTS_TABLE_SIZE = sizeof(TTS_TABLE) / sizeof(TTS_TABLE[0]);

// ── Initialize SPIFFS (flash filesystem) ─────────────────────────
bool speaker_setup() {
    ledcSetup(SPEAKER_PWM_CHANNEL, SPEAKER_PWM_FREQ, SPEAKER_PWM_RESOLUTION);
    ledcAttachPin(DAC_PIN, SPEAKER_PWM_CHANNEL);

    if (!SPIFFS.begin(true)) {
        Serial.println("[SPK] SPIFFS failed — no audio playback");
        return false;
    }
    Serial.println("[SPK] SPIFFS ready");
    return true;
}

// ── Find the WAV file for a given text ───────────────────────────
// Returns nullptr if no match found
const char* speaker_find_file(const String& text) {
    for (int i = 0; i < TTS_TABLE_SIZE; i++) {
        if (text == String(TTS_TABLE[i].text)) {
            return TTS_TABLE[i].file;
        }
    }
    return nullptr;
}

// ── Play a WAV file from SPIFFS ───────────────────────────────────
// Reads 16-bit PCM samples and outputs through PWM on GPIO17
// Sample rate assumed: 8kHz (125 microseconds per sample)
void speaker_play_file(const char* filename) {
    if (!SPIFFS.exists(filename)) {
        Serial.printf("[SPK] File not found: %s\n", filename);
        return;
    }

    File f = SPIFFS.open(filename, "r");
    if (!f) {
        Serial.println("[SPK] Failed to open file");
        return;
    }

    Serial.printf("[SPK] Playing: %s\n", filename);

    f.seek(44);  // skip WAV header (always 44 bytes)

    // Play each 16-bit sample through the DAC
    // DAC only accepts 0-255, but audio is -32768 to +32767
    // So we shift by 128 to center it (silence = 128)
    const int PLAY_SR   = 8000;          // 8kHz playback
    const int DELAY_US  = 1000000 / PLAY_SR;  // 125 microseconds

    while (f.available() >= 2) {
        uint8_t lo = f.read();
        uint8_t hi = f.read();
        int16_t sample16 = (int16_t)((hi << 8) | lo);

        // Map from 16-bit signed → 8-bit unsigned for PWM duty
        uint8_t duty = (uint8_t)((sample16 >> 8) + 128);
        ledcWrite(SPEAKER_PWM_CHANNEL, duty);

        delayMicroseconds(DELAY_US);
    }

    ledcWrite(SPEAKER_PWM_CHANNEL, 128);  // back to silence (midpoint)
    f.close();
}

// ── Main function: play TTS response from backend ─────────────────
// Call this with the tts_text string from the backend JSON response
void speaker_say(const String& text) {
    Serial.printf("[SPK] TTS: %s\n", text.c_str());

    const char* file = speaker_find_file(text);

    if (file == nullptr) {
        Serial.println("[SPK] No matching audio file — text only");
        return;
    }

    speaker_play_file(file);
}