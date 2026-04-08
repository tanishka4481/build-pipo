# POPI — GitHub Copilot Context Prompt

Read this entire file before helping with anything.
This is the full context of the POPI project — what it is,
what is built, what is missing, how everything connects,
and what you need to help complete.

---

## What POPI Is

POPI is a passive, always-present companion toy for children aged 3–5
with speech sound disorders — specifically /s/ phoneme substitution
(e.g. child says "thun" instead of "sun").

It bridges the gap between weekly Speech-Language Pathologist (SLP)
sessions and the 6 days in between. The child never feels like they
are in therapy — they are "teaching the toy to speak."

The device sits on a shelf. When the child walks past it, a proximity
sensor fires, the device wakes up, invites the child to practice, runs
a 90-second micro-session, scores their phoneme productions acoustically,
gives real-time feedback via LED ring + servo + OLED face + TTS speaker,
and logs everything to a cloud server for the SLP to review.

---

## Core Design Rules (Never Break These)

- Therapy in 90-second micro-moments, not formal sessions
- Child is framed as the "teacher" — Facilitative Play technique
  ("Can you help me say sun? I keep getting it wrong!")
- No screens. LED ring + small OLED pixel face only
- No clinical jargon in any child-facing output
- Device always models the target sound BEFORE asking child to attempt
- SLP reviews session data weekly — device works WITHIN clinical relationship
- Methodology mirrors published SLP protocol:
  Assess → Model → Elicit → Feedback → Generalize

---

## Hardware (MVP — breadboard only, no shell yet)

- ESP32-S3 (production target) — WiFi built in, I2S mic support
- For now: Raspberry Pi Zero 2W (hackathon)
- SPH0645 MEMS microphone (I2S)
- 12-pixel NeoPixel LED ring
- SSD1306 128x64 OLED display
- SG90 servo motor
- APDS-9960 proximity sensor
- Small speaker + PAM8403 amp

The hardware is NOT your focus. The server and pipeline are.
Hardware just POSTs audio to the server and acts on the JSON response.

---

## Project Location

```
Desktop/popi/
├── stage1_preprocess.py     ✅ BUILT — do not touch
├── stage2_features.py       ✅ BUILT — do not touch
├── stage3_feedback.py       ✅ BUILT — do not touch
├── stage4_server.py         ✅ BUILT — do not touch unless adding endpoints
├── stage5_tests.py          ✅ BUILT — 36 tests all passing
├── noise_reduction.py       ✅ BUILT — do not touch
├── laptop_demo.py           ✅ BUILT — do not touch
├── analyze_testaudio.py     ✅ BUILT — do not touch
├── config.py                ✅ BUILT — central config, edit thresholds here
├── seed_demo_data.py        ✅ BUILT — seeds demo DB before presentation
├── requirements.txt         ⚠️  EXISTS but needs verification
└── test_audio/              ✅ EXISTS at C:\Users\HP\Desktop\test_audio
    ├── good/
    ├── substitutions/
    └── edge_cases/
```

### Files That Need To Be Created

```
Desktop/popi/
├── requirements.txt         — verify and complete (see section below)
├── render.yaml              — Render deployment config
├── .env.example             — environment variable template
└── README.md                — run instructions for demo day
```

---

## What Each Built File Does

### stage1_preprocess.py
INPUT:  raw WAV bytes (from mic or base64 decode)
OUTPUT: PreprocessResult dataclass
        - fricative_audio: np.ndarray (the /s/ burst segment)
        - quality_ok: bool
        - quality_reason: str

Does: VAD silence stripping, high-pass filter (butter 4th order),
STFT-based fricative detector (HF/LF energy ratio > 1.4),
segments the /s/ burst from full clip.

### stage2_features.py
INPUT:  PreprocessResult from stage1
OUTPUT: FeatureVector dataclass
        - phoneme_score: float (0–1, weighted composite)
        - spectral_centroid: float (Hz)
        - spectral_flatness: float
        - zero_crossing_rate: float
        - fricative_duration: float (seconds)
        - pitch_correct: bool
        - duration_correct: bool
        - quality_ok: bool
        - sub_scores: dict with keys:
            spectral_centroid, spectral_flatness,
            zero_crossing_rate, fricative_duration
        - spectral_match: float

Weights: centroid 40%, flatness 25%, ZCR 20%, duration 15%
Target /s/ values: centroid > 4000Hz, flatness > 0.25, ZCR > 0.18, duration 0.07–0.28s

### stage3_feedback.py
INPUT:  FeatureVector + SessionState
OUTPUT: FeedbackDecision dataclass
        - feedback_type: str (praise | corrective | model | no_attempt)
        - led_state: str
        - face_state: str
        - servo_action: str
        - tts_text: str
        - advance: bool
        - drop_back: bool
        - hint: str (which sub-feature was weakest)

Thresholds:
  score >= 0.70 → praise path
  score 0.45–0.70 → corrective path (directional hint)
  score < 0.45 → model path (device demonstrates sound again)

SessionState tracks: consecutive passes, consecutive fails,
current_level. Advance after 3 passes, drop after 3 fails.

### stage4_server.py
FastAPI server. Wraps stages 1–3 into HTTP endpoints.
Uses SQLAlchemy + SQLite (swap to PostgreSQL in production).

EXISTING ENDPOINTS:
  POST /session/start     → {session_id, level, message}
  POST /attempt           → full pipeline, writes DB, returns JSON
  GET  /session/{id}      → session summary for SLP
  GET  /health            → liveness check

NEW ENDPOINTS (already added):
  GET  /ping              → keep Render free tier warm
  POST /session/end       → close session, clear memory state
  POST /child/create      → register child (name, age, phoneme, notes)
  GET  /children          → list all children for dashboard home
  GET  /child/{id}        → full profile + session history + daily scores
  POST /plan/push         → SLP prescribes word list for the week
  GET  /plan/sync         → device calls this on wake, gets word list
  GET  /alerts/{child_id} → fetch undismissed alerts
  POST /alert/dismiss     → SLP dismisses alert
  GET  /word-bank         → full word bank for dashboard planner

DB TABLES:
  children    — id, name, age, disorder_type, target_phoneme, slp_id, notes
  word_plans  — id, child_id, week_start, word_list(JSON), start_level,
                pass_threshold, max_attempts, pushed_at, synced_at
  sessions    — id, child_id, started_at, ended_at, level,
                target_phoneme, total_attempts, final_score_avg
  attempts    — id, session_id, child_id, timestamp, attempt_number,
                level, target_phoneme, target_word, phoneme_score,
                feedback_type, hint, sub_centroid, sub_flatness,
                sub_zcr, sub_duration, raw_centroid_hz, raw_duration_ms,
                pitch_correct, duration_correct, led_state, face_state,
                advance_triggered, drop_triggered
  alerts      — id, child_id, alert_type(parent|slp), category,
                message, created_at, dismissed_at, dismissed_by

/attempt REQUEST (multipart/form-data):
  session_id, child_id, attempt_number, current_level,
  target_phoneme, target_word, audio (file) OR audio_b64 (base64 str)

/attempt RESPONSE (JSON):
  score, feedback_type, led_state, face_state, servo_action,
  tts_text, advance, drop_back, new_level, db_written,
  hint, sub_scores (dict), diagnostic (dict)

### stage5_tests.py
36 tests across 4 layers. ALL PASSING. Do not break these.
Layer 1: unit tests per stage
Layer 2: acoustic realism (room noise, /th/ sub, /f/ sub, whisper, clipping)
Layer 3: therapy arc scenarios (advance, plateau, drop, mixed session)
Layer 4: regression tests (fixed seed, expected ranges)

Run: python3 stage5_tests.py --quick

### noise_reduction.py
Spectral subtraction noise reduction.
INPUT:  raw WAV bytes
OUTPUT: clean WAV bytes
Usage:  clean_bytes = denoise(raw_bytes)
Called before stage1 in the /attempt pipeline.

### laptop_demo.py
Full demo that runs on laptop. No hardware needed.
Uses laptop mic OR synthetic audio (--synthetic flag).
Terminal UI simulates LED ring, OLED face, score bar, sub-scores.

Usage:
  python3 stage4_server.py          # terminal 1
  python3 laptop_demo.py            # terminal 2
  python3 laptop_demo.py --selfhost # one-shot (starts server automatically)
  python3 laptop_demo.py --synthetic --selfhost  # no mic needed

### analyze_testaudio.py
Runs full pipeline on a folder of audio files.
Prints table: filename, quality, score, centroid, flatness, ZCR, duration,
feedback type, hint, and classification label.
Test audio is at: C:\Users\HP\Desktop\test_audio

Usage:
  python3 analyze_testaudio.py
  python3 analyze_testaudio.py --folder "C:\Users\HP\Desktop\test_audio\good"

### config.py
Central configuration. ALL thresholds, constants, and word bank here.
If you need to change a threshold or add words, do it here only.

Key values:
  PRAISE_THRESHOLD     = 0.70
  CORRECTIVE_THRESHOLD = 0.45
  ADVANCE_STREAK       = 3
  DROP_STREAK          = 3
  PARK_THRESHOLD       = 3
  LEVELS               = [phoneme, syllable, word_init, word_final, word_med, phrase]
  WORD_BANK            = dict of lists by level, each item has {word, prompt}
  TTS_PRAISE/CORRECTIVE/MODEL/LEVEL_UP = list of strings (Facilitative Play framing)

### seed_demo_data.py
Seeds the DB with 5 days of realistic improving data for demo day.
Creates child "Arjun", pushes word plan, seeds sessions.
Score trend: 0.40 → 0.70 (improving week over week).

Usage:
  python3 seed_demo_data.py
  python3 seed_demo_data.py --server https://popi-api.onrender.com

---

## How Everything Connects (Full Data Flow)

```
SLP Dashboard (future — not built yet)
  POST /plan/push → pushes word list to server
        ↓
Cloud Server (FastAPI on Render)
  stores word plan in DB
        ↓
Device (ESP32-S3 / RPi Zero 2W) wakes on proximity
  GET /plan/sync → pulls word list
  POST /session/start → gets session_id
        ↓
Child attempts phoneme
  Device records 2s audio via I2S mic
  POST /attempt with base64 WAV
        ↓
Server pipeline:
  noise_reduction → stage1 → stage2 → stage3
  writes DB
  checks alert conditions
  returns JSON: {score, led_state, face_state,
                 servo_action, tts_text, advance,
                 drop_back, new_level, sub_scores}
        ↓
Device acts on JSON:
  LED ring → NeoPixel animation
  Servo → PWM routine
  OLED → pixel face frame
  Speaker → TTS text
        ↓
Session ends
  POST /session/end
  Server evaluates alerts
  Parent notification if no practice 2+ days
  SLP alert if centroid low 3+ days
        ↓
SLP reviews data (future dashboard)
  GET /child/{id} → full history, daily scores
  GET /alerts/{child_id} → clinical flags
  Next week: POST /plan/push with new words
```

---

## Hosting

**Server: Render (free tier)**
- Deploy from GitHub
- Auto HTTPS at https://popi-api.onrender.com
- Free tier spins down after 15 min inactivity
- Fix: cron-job.org pings /ping every 10 minutes (free)
- Persistent disk for SQLite: 1GB free, mount at /data
- Set DATABASE_URL env var to: sqlite:////data/popi.db

**Database: SQLite on Render persistent disk**
- Zero config change from local dev
- File at /data/popi.db on Render
- Survives redeploys if persistent disk is mounted
- Not for production at scale — fine for hackathon

**Dashboard: NOT BUILT YET**
- Will be React on Vercel (free)
- Do not build dashboard now
- All server endpoints are ready for it

**Local dev:**
- python3 stage4_server.py → runs on localhost:8000
- DATABASE_URL defaults to sqlite:///./popi.db

---

## Files You Need to Create

### 1. requirements.txt
Verify and complete. Must include at minimum:

```
fastapi
uvicorn[standard]
sqlalchemy
pydantic
numpy
scipy
librosa
soundfile
sounddevice
rich
requests
python-multipart
```

Check imports across all stage files and add anything missing.
Do not add packages not actually used.

### 2. render.yaml
Render deployment config. Should be:

```yaml
services:
  - type: web
    name: popi-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn stage4_server:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        value: sqlite:////data/popi.db
    disk:
      name: popi-db
      mountPath: /data
      sizeGB: 1
```

### 3. .env.example
Template for environment variables:

```
DATABASE_URL=sqlite:///./popi.db
HOST=0.0.0.0
PORT=8000
```

### 4. README.md
Must include:
- What POPI is (2 sentences)
- Install instructions
- How to run locally (server + demo)
- How to run tests
- How to seed demo data
- How to deploy to Render
- Run order for demo day

---

## Adaptive Logic (Implemented in stage3_feedback.py + SessionState)

```
Per word per session:
  Same word fails twice in a row → drop to phoneme isolation for that word
  Same word fails 3 times → park word, move to next word on list
  Park logged in DB for SLP review

Per session:
  3 consecutive passes → advance level
  3 consecutive fails  → drop level

Across days (server-side alert logic in stage4_server.py):
  Centroid low for 3+ days → SLP alert (placement regression)
  No practice for 2 days  → parent alert
  No practice for 3 days  → SLP alert
```

---

## Level Ladder

```
0 — phoneme     pure /s/ isolation ("make the wind sound")
1 — syllable    /s/ + vowel ("sss-ee")
2 — word_init   initial position ("sun", "sea", "sock")
3 — word_final  final position ("bus", "house")
4 — word_med    medial position ("biscuit", "outside")
5 — phrase      full phrase ("the sun is hot")
```

Child never attempts word level without phoneme isolation check first.
Every session starts with a quick phoneme confirmation before prescribed words.

---

## Display States (for reference — hardware team uses these)

```
Idle:         slow_pulse_blue    | (-_-) zzz      | still
Wake:         warm_pulse_white   | (O_O)           | big wiggle
Invitation:   breathe_cyan       | (•ᴗ•)?          | slow tilt
Modeling:     soft_cyan_ripple   | mouth animating | none
Listening:    reactive to Hz     | (o_o) attentive | lean forward
Score>=0.70:  burst_green        | ^‿^             | nod fast
Score 0.45+:  breathe_yellow     | (•ᴗ•)? tilt     | slow tilt
Score<0.45:   slow_red_pulse     | (>_<)           | none
Level up:     rainbow_spin       | \(^o^)/         | celebrate
Goodbye:      warm_fade_amber    | (^_^) wave      | wave motion
```

---

## What NOT to Do

- Do NOT build the dashboard frontend (React) — that is later
- Do NOT change stage1, stage2, stage3 files — they are validated
- Do NOT change stage5_tests.py — all 36 tests pass, keep them passing
- Do NOT add clinical jargon to any tts_text field
- Do NOT use keyword spotting (checking if child said the right word)
  We score acoustics (HOW they said it), not semantics (WHAT they said)
- Do NOT add authentication — not needed for hackathon
- Do NOT use PostgreSQL — SQLite is fine for now
- Do NOT use Redis — in-memory dict for session state is fine for now

---

## Key Things to Understand Before Helping

1. The ML pipeline scores ACOUSTIC FEATURES not words.
   centroid, ZCR, flatness, duration — these are DSP features.
   There is no speech-to-text anywhere in this pipeline.

2. The child is always the teacher. Every TTS string uses
   Facilitative Play framing. Device asks for help, never corrects.

3. The SLP prescribes words on Monday. Device uses those words
   Tuesday–Sunday. SLP reviews data next Monday.
   This loop is the entire product.

4. Feedback is directional not binary.
   Not "wrong" — "the wind sound needs more air"
   Not "right" — "yes! you helped me!"

5. The device works offline during sessions.
   It syncs word plan on wake, runs session fully,
   pushes attempt data after. WiFi drop mid-session = 
   fall back to local scorer, buffer attempts, push when reconnected.

---

## Demo Day Run Order

```bash
# 1. Start server
python3 stage4_server.py

# 2. Seed demo data (run once)
python3 seed_demo_data.py

# 3. Run live demo
python3 laptop_demo.py --selfhost

# 4. If no mic available
python3 laptop_demo.py --synthetic --selfhost

# 5. Quick regression check before demo
python3 stage5_tests.py --quick

# 6. Test on real audio files
python3 analyze_testaudio.py --folder "C:\Users\HP\Desktop\test_audio"
```

---

## One-Line Answers to Hard Questions (Know These)

- "Clinical validation?" → Methodology mirrors published SLP protocol. Trial is phase 2.
- "Wrong sound scores high?" → cat.wav scored 0.53, routed to model path. 10/10 real audio.
- "Just a toy?" → Yes. Clinical methodology invisible to child. They play. We measure.
- "Tongue placement?" → SLP teaches Monday. We give 180 repetitions motor memory needs Tuesday–Sunday.
- "Why not an app?" → Apps do keyword spotting. We score acoustics. We know WHY it failed.
- "Why not Alexa?" → Alexa understands what you said. We understand how you said it.
- "Hindi support?" → Pipeline is language-agnostic. TTS needs localisation. Content problem, not architecture.

---

Now help me with whatever I ask next.
All code you write must be consistent with this context.
All file paths are relative to Desktop/popi/ unless stated otherwise.
