// ================================================================
// MODULE 3 — MICROPHONE (INMP441)
// ================================================================
// Sets up the INMP441 digital microphone and records audio.
//
// How the INMP441 works:
//   - It's a digital mic — it sends audio as numbers, not voltage
//   - It uses a protocol called I2S (Inter-IC Sound)
//   - I2S needs 3 wires: Clock (SCK), Word Select (WS), Data (SD)
//   - It sends 32-bit numbers but only the top 18 bits are real
//     audio. We keep only the top 16 bits (standard PCM format).
//
// What mic_record() does:
//   1. Waits for the button to be held
//   2. Records until button released OR 4 seconds passed
//   3. Writes a proper .WAV file into the audio buffer
//   4. Returns how many bytes were written (0 = too short)
// ================================================================

#pragma once
#include <Arduino.h>
#include <driver/i2s.h>
#include "1_config.h"

// The audio buffer — lives in global memory, allocated in setup()
extern uint8_t* audioBuffer;
extern size_t   audioBytes;

// ── Write a WAV file header ───────────────────────────────────────
//
// A WAV file = 44-byte header + raw PCM audio data.
// The header tells any software: "this is audio at 16kHz, mono, 16-bit"
// Without it, the backend can't decode the file.
//
void mic_write_wav_header(uint8_t* buf, uint32_t pcmDataSize) {
    uint32_t fileSize  = pcmDataSize + 36;
    uint32_t byteRate  = SAMPLE_RATE * 2;  // 2 bytes per sample (16-bit)

    // RIFF chunk descriptor
    buf[0]='R'; buf[1]='I'; buf[2]='F'; buf[3]='F';
    buf[4]=(fileSize)&0xFF;      buf[5]=(fileSize>>8)&0xFF;
    buf[6]=(fileSize>>16)&0xFF;  buf[7]=(fileSize>>24)&0xFF;
    buf[8]='W'; buf[9]='A'; buf[10]='V'; buf[11]='E';

    // fmt sub-chunk (describes the audio format)
    buf[12]='f'; buf[13]='m'; buf[14]='t'; buf[15]=' ';
    buf[16]=16; buf[17]=0; buf[18]=0; buf[19]=0;  // sub-chunk size = 16
    buf[20]=1;  buf[21]=0;   // audio format = PCM (uncompressed)
    buf[22]=1;  buf[23]=0;   // channels = 1 (mono)
    buf[24]=(SAMPLE_RATE)&0xFF;      buf[25]=(SAMPLE_RATE>>8)&0xFF;
    buf[26]=(SAMPLE_RATE>>16)&0xFF;  buf[27]=(SAMPLE_RATE>>24)&0xFF;
    buf[28]=(byteRate)&0xFF;         buf[29]=(byteRate>>8)&0xFF;
    buf[30]=(byteRate>>16)&0xFF;     buf[31]=(byteRate>>24)&0xFF;
    buf[32]=2;  buf[33]=0;   // block align = 2 bytes
    buf[34]=16; buf[35]=0;   // bits per sample = 16

    // data sub-chunk
    buf[36]='d'; buf[37]='a'; buf[38]='t'; buf[39]='a';
    buf[40]=(pcmDataSize)&0xFF;      buf[41]=(pcmDataSize>>8)&0xFF;
    buf[42]=(pcmDataSize>>16)&0xFF;  buf[43]=(pcmDataSize>>24)&0xFF;
}

// ── Initialize the I2S microphone ────────────────────────────────
void mic_setup() {
    // I2S configuration for INMP441
    i2s_config_t cfg = {
        .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate          = SAMPLE_RATE,
        .bits_per_sample      = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,  // L/R pin → GND = left
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count        = 8,
        .dma_buf_len          = 512,
        .use_apll             = false,
        .tx_desc_auto_clear   = false,
        .fixed_mclk           = 0,
    };

    i2s_pin_config_t pins = {
        .bck_io_num   = MIC_SCK_PIN,
        .ws_io_num    = MIC_WS_PIN,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num  = MIC_SD_PIN,
    };

    i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
    i2s_set_pin(I2S_NUM_0, &pins);
    i2s_zero_dma_buffer(I2S_NUM_0);

    Serial.println("[MIC] INMP441 ready at 16kHz");
}

// ── Record audio while button is held ────────────────────────────
//
// Returns: total bytes in audioBuffer (WAV header + PCM data)
//          OR 0 if the recording was too short to be useful
//
size_t mic_record() {
    uint8_t* pcmStart   = audioBuffer + 44;   // skip 44 bytes for header
    size_t   pcmBytes   = 0;
    uint32_t maxPcm     = SAMPLE_RATE * 2 * (MAX_REC_MS / 1000);
    uint32_t minPcm     = SAMPLE_RATE * 2 * (MIN_REC_MS / 1000);
    uint32_t startMs    = millis();

    Serial.println("[MIC] Recording — hold the button...");

    // Record while button held AND under 4 second limit
    while (digitalRead(BUTTON_PIN) == LOW && pcmBytes < maxPcm) {

        int32_t samples32[64];   // temporary buffer for 32-bit I2S samples
        size_t  bytesRead = 0;

        // Read a chunk of samples from the mic
        i2s_read(I2S_NUM_0, samples32, sizeof(samples32),
                 &bytesRead, portMAX_DELAY);

        int count = bytesRead / 4;  // 4 bytes per 32-bit sample
        for (int i = 0; i < count && pcmBytes < maxPcm; i++) {
            // Convert 32-bit → 16-bit by taking the top 16 bits
            int16_t s16 = (int16_t)(samples32[i] >> 16);

            // Store as little-endian (standard WAV format)
            pcmStart[pcmBytes++] = s16 & 0xFF;
            pcmStart[pcmBytes++] = (s16 >> 8) & 0xFF;
        }
    }

    uint32_t duration = millis() - startMs;
    Serial.printf("[MIC] Recorded %d bytes in %d ms\n", (int)pcmBytes, (int)duration);

    // Reject if too short — backend needs at least 150ms
    if (pcmBytes < minPcm) {
        Serial.println("[MIC] Too short — ignored");
        return 0;
    }

    // Write WAV header at the start of the buffer
    mic_write_wav_header(audioBuffer, pcmBytes);
    return 44 + pcmBytes;
}