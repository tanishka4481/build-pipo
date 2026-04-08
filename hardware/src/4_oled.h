// ================================================================
// MODULE 4 — OLED ANIMATIONS
// ================================================================
// Draws animated faces on the SSD1306 OLED screen.
//
// The backend sends a "face_state" string with every response.
// This module maps those strings to actual drawings on screen.
//
// Face states from the backend (stage3_feedback.py):
//   "waiting_blink"    → idle, blinking face (child hasn't spoken yet)
//   "big_happy"        → big smile (correct answer)
//   "celebrate_bounce" → bouncing + stars (level up!)
//   "curious_tilt"     → curious face (almost correct, try again)
//   "sad_then_model"   → sad face (wrong, listen to me)
//   "confused_tilt"    → confused face (no clear sound detected)
//
// How animation works:
//   - We have an animFrame counter (0-7) that increments every 125ms
//   - Each face uses animFrame to decide which frame to draw
//   - This creates the blinking / bouncing effect
// ================================================================

#pragma once
#include <Adafruit_SSD1306.h>
#include "1_config.h"

extern Adafruit_SSD1306 display;

// Animation state — which face to show right now
enum FaceState {
    FACE_IDLE,        // Blinking, waiting for button press
    FACE_LISTENING,   // Wide eyes, recording in progress
    FACE_THINKING,    // Thinking dots, waiting for backend reply
    FACE_HAPPY,       // Big smile (score >= 0.70)
    FACE_CELEBRATE,   // Bouncing + stars (level up)
    FACE_CURIOUS,     // One big eye, curious (corrective feedback)
    FACE_SAD,         // Frown (wrong phoneme / model the sound)
    FACE_ERROR        // No WiFi or backend error
};

FaceState currentFace = FACE_IDLE;
uint8_t   animFrame   = 0;
uint32_t  lastFrameMs = 0;
uint32_t  faceStartMs = 0;

// ── Helper: draw eye ──────────────────────────────────────────────
// cx, cy = center of eye. closed = just a line. wide = bigger circle.
void drawEye(int cx, int cy, bool closed, bool wide) {
    if (closed) {
        display.drawLine(cx - 3, cy, cx + 3, cy, WHITE);
    } else if (wide) {
        display.fillCircle(cx, cy, 5, WHITE);
        display.fillCircle(cx, cy, 2, BLACK);  // pupil
    } else {
        display.fillCircle(cx, cy, 3, WHITE);
        display.fillCircle(cx, cy, 1, BLACK);  // pupil
    }
}

// ── Helper: draw mouth ────────────────────────────────────────────
// type 0=neutral  1=small smile  2=big smile  3=frown
void drawMouth(int cx, int cy, int type) {
    switch (type) {
        case 0:  // neutral line
            display.drawLine(cx - 5, cy, cx + 5, cy, WHITE);
            break;
        case 1:  // small smile (3 lines making a curve)
            display.drawLine(cx - 5, cy,     cx - 2, cy + 2, WHITE);
            display.drawLine(cx - 2, cy + 2, cx + 2, cy + 2, WHITE);
            display.drawLine(cx + 2, cy + 2, cx + 5, cy,     WHITE);
            break;
        case 2:  // big smile (wider arc)
            display.drawLine(cx - 7, cy - 1, cx - 4, cy + 3, WHITE);
            display.drawLine(cx - 4, cy + 3, cx,     cy + 5, WHITE);
            display.drawLine(cx,     cy + 5, cx + 4, cy + 3, WHITE);
            display.drawLine(cx + 4, cy + 3, cx + 7, cy - 1, WHITE);
            break;
        case 3:  // frown
            display.drawLine(cx - 5, cy + 2, cx - 2, cy,     WHITE);
            display.drawLine(cx - 2, cy,     cx + 2, cy,     WHITE);
            display.drawLine(cx + 2, cy,     cx + 5, cy + 2, WHITE);
            break;
    }
}

// ── Helper: draw face outline ─────────────────────────────────────
void drawFaceOutline(int cx, int cy) {
    display.drawCircle(cx, cy, 18, WHITE);
}

// ── Individual face drawers ───────────────────────────────────────
// cx, cy = center of the face on screen

void drawFace_Idle(int cx, int cy, uint8_t frame) {
    drawFaceOutline(cx, cy);
    bool blink = (frame == 7);   // blink on frame 7 (once per cycle)
    drawEye(cx - 6, cy - 3, blink, false);
    drawEye(cx + 6, cy - 3, blink, false);
    drawMouth(cx, cy + 6, 0);
}

void drawFace_Listening(int cx, int cy) {
    drawFaceOutline(cx, cy);
    drawEye(cx - 6, cy - 3, false, true);  // wide eyes = attentive
    drawEye(cx + 6, cy - 3, false, true);
    drawMouth(cx, cy + 6, 0);
}

void drawFace_Thinking(int cx, int cy) {
    drawFaceOutline(cx, cy);
    drawEye(cx - 6, cy - 3, false, false);
    drawEye(cx + 6, cy - 3, false, false);
    drawMouth(cx, cy + 6, 0);
    // Thought bubble dots (top right of face)
    display.fillCircle(cx + 16, cy - 16, 2, WHITE);
    display.fillCircle(cx + 20, cy - 20, 3, WHITE);
}

void drawFace_Happy(int cx, int cy, uint8_t frame) {
    drawFaceOutline(cx, cy);
    bool squint = (frame % 2 == 0);  // eyes squint on alternate frames
    drawEye(cx - 6, cy - 3, squint, false);
    drawEye(cx + 6, cy - 3, squint, false);
    drawMouth(cx, cy + 5, 2);
}

void drawFace_Celebrate(int cx, int cy, uint8_t frame) {
    int bounce = (frame % 2 == 0) ? 0 : -4;  // bounce up/down
    drawFace_Happy(cx, cy + bounce, frame);
    // Stars in corners
    display.setCursor(0, 0);   display.print("*");
    display.setCursor(118, 0); display.print("*");
}

void drawFace_Curious(int cx, int cy) {
    drawFaceOutline(cx, cy);
    drawEye(cx - 6, cy - 3, false, true);   // left eye wide
    drawEye(cx + 6, cy - 3, false, false);  // right eye normal
    drawMouth(cx, cy + 6, 1);
    // Question mark
    display.setCursor(cx + 20, cy - 8);
    display.setTextSize(1);
    display.print("?");
}

void drawFace_Sad(int cx, int cy) {
    drawFaceOutline(cx, cy);
    drawEye(cx - 6, cy - 3, false, false);
    drawEye(cx + 6, cy - 3, false, false);
    drawMouth(cx, cy + 7, 3);
}

void drawFace_Error(int cx, int cy) {
    // Simple X face for error
    display.drawLine(cx - 5, cy - 5, cx + 5, cy + 5, WHITE);
    display.drawLine(cx + 5, cy - 5, cx - 5, cy + 5, WHITE);
    display.drawLine(cx - 5, cy + 10, cx + 5, cy + 10, WHITE);  // flat mouth
}

// ── Main render function — call this from loop() ──────────────────
//
// Clears screen, draws the current face + bottom status text,
// then pushes to display. Call every 125ms for smooth animation.
//
void oled_render() {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(WHITE);

    int cx = 64;  // face center X (middle of 128px screen)
    int cy = 28;  // face center Y (upper half of 64px screen)

    switch (currentFace) {
        case FACE_IDLE:
            drawFace_Idle(cx, cy, animFrame);
            display.setCursor(15, 54);
            display.print("Press to speak!");
            break;

        case FACE_LISTENING:
            drawFace_Listening(cx, cy);
            display.setCursor(30, 54);
            display.print("Listening...");
            // Pulsing dot to show it's recording
            if ((millis() / 400) % 2 == 0)
                display.fillCircle(64, 48, 2, WHITE);
            break;

        case FACE_THINKING: {
            drawFace_Thinking(cx, cy);
            display.setCursor(38, 54);
            display.print("Hmm");
            // Animated dots: "Hmm." → "Hmm.." → "Hmm..."
            int dots = (millis() / 400) % 4;
            for (int d = 0; d < dots; d++) display.print(".");
            break;
        }

        case FACE_HAPPY:
            drawFace_Happy(cx, cy, animFrame);
            display.setCursor(22, 54);
            display.print("Great job! :)");
            break;

        case FACE_CELEBRATE:
            drawFace_Celebrate(cx, cy, animFrame);
            display.setCursor(18, 54);
            display.print("Level up!  :D");
            break;

        case FACE_CURIOUS:
            drawFace_Curious(cx, cy);
            display.setCursor(28, 54);
            display.print("Try again!");
            break;

        case FACE_SAD:
            drawFace_Sad(cx, cy);
            display.setCursor(28, 54);
            display.print("Hear me...");
            break;

        case FACE_ERROR:
            drawFace_Error(cx, cy);
            display.setCursor(14, 54);
            display.print("No connection");
            break;
    }

    display.display();

    // Advance animation frame every 125ms
    if (millis() - lastFrameMs > 125) {
        animFrame   = (animFrame + 1) % 8;
        lastFrameMs = millis();
    }
}

// ── Set the current face ──────────────────────────────────────────
// Call this whenever you want to change what's on screen.
void oled_set_face(FaceState face) {
    currentFace = face;
    animFrame   = 0;
    faceStartMs = millis();
    oled_render();  // draw immediately, don't wait for next loop tick
}

// ── Map backend string → FaceState ───────────────────────────────
// The backend sends strings like "big_happy" — this converts them.
void oled_set_from_backend(const String& faceState, bool advance) {
    if (advance) {
        oled_set_face(FACE_CELEBRATE);
    } else if (faceState == "big_happy" || faceState == "celebrate_bounce") {
        oled_set_face(FACE_HAPPY);
    } else if (faceState == "curious_tilt") {
        oled_set_face(FACE_CURIOUS);
    } else if (faceState == "sad_then_model" || faceState == "confused_tilt") {
        oled_set_face(FACE_SAD);
    } else if (faceState == "waiting_blink") {
        oled_set_face(FACE_IDLE);
    } else {
        oled_set_face(FACE_IDLE);
    }
}