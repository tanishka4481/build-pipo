"""
Stage 3 — Feedback Decision Engine
=====================================
Input  : FeatureVector from Stage 2  +  SessionState (attempt history)
Output : FeedbackDecision dataclass with everything the RPi needs:

    led_state       str   — animation name for LED ring
    face_state      str   — animation name for OLED character
    servo_action    str   — what the servo does
    tts_text        str   — what the device says out loud
    feedback_type   str   — label for DB ("praise" | "corrective" | "model")
    advance         bool  — tell RPi to move up a difficulty level
    drop_back       bool  — tell RPi to drop down a level
    hint            str   — which specific feature to address (for diagnostic logging)

SessionState tracks:
    current_level   str   — discrimination | isolation | syllable | word | phrase
    consecutive_pass int  — streak of scores >= PASS_THRESHOLD
    consecutive_fail int  — streak of scores <  FAIL_THRESHOLD
    attempt_history list  — last N FeatureVectors for trend analysis

Adaptive rule (mirrors SLP methodology):
    3 consecutive passes (score >= 0.70) → advance
    3 consecutive fails  (score <  0.45) → drop_back
    Mixed → stay, give directional feedback

Feedback is DIRECTIONAL not binary:
    The device never says "wrong". It says what to fix:
    - centroid low  → "make it hissier / more air through your teeth"
    - flatness low  → "let the air flow smoothly"  
    - duration low  → "hold it a bit longer — ssssss"
    - duration high → "good sound! try a shorter one"
    - all good      → praise + advance check
"""

from dataclasses import dataclass, field
from typing import Optional
import random
from stage2_features import FeatureVector, WEIGHTS

# ── Thresholds ─────────────────────────────────────────────────────────────────
PASS_THRESHOLD   = 0.70   # score >= this = pass
FAIL_THRESHOLD   = 0.45   # score <  this = fail
ADVANCE_STREAK   = 3      # consecutive passes needed to advance
DROP_STREAK      = 3      # consecutive fails needed to drop back

# Sub-score threshold below which we flag that feature as "the problem"
SUB_SCORE_WEAK   = 0.55

# Difficulty levels in order
LEVELS = ["discrimination", "isolation", "syllable", "word", "phrase"]

# ── Output dataclasses ─────────────────────────────────────────────────────────

@dataclass
class SessionState:
    current_level:     str   = "isolation"
    consecutive_pass:  int   = 0
    consecutive_fail:  int   = 0
    attempt_history:   list  = field(default_factory=list)   # list of scores

    def record(self, score: float):
        self.attempt_history.append(round(score, 4))
        if score >= PASS_THRESHOLD:
            self.consecutive_pass += 1
            self.consecutive_fail  = 0
        elif score < FAIL_THRESHOLD:
            self.consecutive_fail += 1
            self.consecutive_pass  = 0
        else:
            # mid-range — break both streaks
            self.consecutive_pass = 0
            self.consecutive_fail = 0

    def level_index(self) -> int:
        return LEVELS.index(self.current_level) if self.current_level in LEVELS else 1

    def advance_level(self):
        idx = self.level_index()
        if idx < len(LEVELS) - 1:
            self.current_level    = LEVELS[idx + 1]
            self.consecutive_pass = 0
            self.consecutive_fail = 0

    def drop_level(self):
        idx = self.level_index()
        if idx > 0:
            self.current_level    = LEVELS[idx - 1]
            self.consecutive_pass = 0
            self.consecutive_fail = 0


@dataclass
class FeedbackDecision:
    led_state:      str
    face_state:     str
    servo_action:   str
    tts_text:       str
    feedback_type:  str   # "praise" | "corrective" | "model" | "no_attempt"
    advance:        bool  = False
    drop_back:      bool  = False
    hint:           str   = ""   # which feature was weakest — for DB


# ── Public entry point ─────────────────────────────────────────────────────────

def decide(fv: FeatureVector, state: SessionState) -> FeedbackDecision:
    """
    Main entry. Takes a FeatureVector + mutable SessionState.
    Updates state in place (records attempt, advances/drops level).
    Returns a FeedbackDecision.
    """

    # ── Case 0: no attempt / silent ──────────────────────────────────────────
    if fv.phoneme_score == 0.0 and not fv.quality_ok:
        return FeedbackDecision(
            led_state    = "slow_pulse_blue",
            face_state   = "waiting_blink",
            servo_action = "none",
            tts_text     = _pick("no_attempt"),
            feedback_type= "no_attempt",
            hint         = "no_audio",
        )

    # ── Case 1: audio present but no fricative (substitution / wrong phoneme) ─
    if not fv.quality_ok and fv.phoneme_score > 0.0:
        state.record(fv.phoneme_score)
        advance, drop = _check_streaks(state)
        _apply_level_change(state, advance, drop)
        return FeedbackDecision(
            led_state    = "slow_red_pulse",
            face_state   = "confused_tilt",
            servo_action = "none",
            tts_text     = _pick("model_sound", level=state.current_level),
            feedback_type= "model",
            advance      = advance,
            drop_back    = drop,
            hint         = "wrong_phoneme",
        )

    # ── Normal path: quality_ok = True ───────────────────────────────────────
    score = fv.phoneme_score
    state.record(score)
    advance, drop = _check_streaks(state)
    _apply_level_change(state, advance, drop)

    # find the weakest sub-score to give directional hint
    weakest_feature, weakest_score = _find_weakness(fv)

    # ── Case 2: great attempt ─────────────────────────────────────────────────
    if score >= PASS_THRESHOLD:
        return FeedbackDecision(
            led_state    = "burst_green" if not advance else "rainbow_spin",
            face_state   = "big_happy"   if not advance else "celebrate_bounce",
            servo_action = "nod_fast",
            tts_text     = _pick("praise", advance=advance, level=state.current_level),
            feedback_type= "praise",
            advance      = advance,
            drop_back    = False,
            hint         = "none",
        )

    # ── Case 3: close attempt — give directional hint ─────────────────────────
    if score >= FAIL_THRESHOLD:
        hint_text = _hint_text(weakest_feature, fv)
        return FeedbackDecision(
            led_state    = "breathe_yellow",
            face_state   = "curious_tilt",
            servo_action = "slow_tilt",
            tts_text     = hint_text,
            feedback_type= "corrective",
            advance      = False,
            drop_back    = drop,
            hint         = weakest_feature,
        )

    # ── Case 4: weak attempt — model the sound ───────────────────────────────
    return FeedbackDecision(
        led_state    = "slow_red_pulse",
        face_state   = "sad_then_model",
        servo_action = "none",
        tts_text     = _pick("model_sound", level=state.current_level),
        feedback_type= "model",
        advance      = False,
        drop_back    = drop,
        hint         = weakest_feature,
    )


# ── Adaptive logic ─────────────────────────────────────────────────────────────

def _check_streaks(state: SessionState) -> tuple[bool, bool]:
    advance  = state.consecutive_pass >= ADVANCE_STREAK
    drop     = state.consecutive_fail >= DROP_STREAK
    return advance, drop

def _apply_level_change(state: SessionState, advance: bool, drop: bool):
    if advance:
        state.advance_level()
    elif drop:
        state.drop_level()


# ── Weakness detection ────────────────────────────────────────────────────────

def _find_weakness(fv: FeatureVector) -> tuple[str, float]:
    """Return the sub-score name and value that is most below SUB_SCORE_WEAK."""
    subs = fv.sub_scores
    # weight-adjusted weakness: a weak high-weight feature matters more
    weighted = {k: (1.0 - subs.get(k, 1.0)) * WEIGHTS[k] for k in WEIGHTS}
    worst = max(weighted, key=weighted.get)
    return worst, subs.get(worst, 0.0)


# ── TTS text banks ────────────────────────────────────────────────────────────
# All language is from the child's POV ("help me learn") — Facilitative Play frame

_TTS = {
    "no_attempt": [
        "Hmm, I didn't quite hear that. Can you try again?",
        "I'm listening... can you help me?",
        "Oops, I missed it! One more time?",
    ],
    "praise": [
        "Yes! You're so good at teaching me!",
        "That's it! I felt it — ssss — just like that!",
        "Wow, you're amazing at this!",
        "Perfect! I almost got it — do it one more time?",
        "I heard it! You're a great teacher!",
    ],
    "praise_advance": [
        "You've taught me so well, let's try something harder!",
        "You're SO good at this — ready for the next challenge?",
        "Level up! You're the best teacher I've ever had!",
    ],
    "model_isolation": [
        "Hmm, I'm confused. Listen to how I do it — ssssss. Now you try!",
        "Let me show you — ssssss — like air through your teeth. Your turn!",
        "I need your help! The sound is like a snake — ssssss. Try?",
    ],
    "model_syllable": [
        "Ooh, let's try the whole piece — sss-un. Can you copy me?",
        "Together now — ssss-ay. Your turn!",
        "Listen — sss-ee. Now you help me say it!",
    ],
    "model_word": [
        "The whole word now — sssnake. Can you teach me?",
        "Let's do it — sssun. You try!",
        "Hear me — ssstar. Now copy that!",
    ],
    "model_phrase": [
        "Try the whole thing — the sssnake is silly. Your turn!",
        "All together — ssee the ssun. Can you say that?",
    ],
}

# Directional corrective hints — mapped to specific weak features
_HINTS = {
    "spectral_centroid": [
        "Ooh so close! Try pushing more air through your front teeth — ssssss.",
        "Almost! Make the sound sharper — like a hiss. Teeth together, ssss!",
        "I need more hiss! Try making your tongue stay low and push air out.",
    ],
    "spectral_flatness": [
        "Nice try! Keep the air flowing smoothly — don't stop it, ssssss.",
        "So close! Let the air stream out steadily — like a slow hiss.",
        "Almost! Relax your tongue a bit and let the air out — sssss.",
    ],
    "zero_crossing_rate": [
        "Good effort! Try making it crispier — ssss — lots of tiny vibrations!",
        "Close! The sound needs to be a bit buzzier — ssss like a bee!",
        "Almost there! Make it sharper and more buzzy — ssssss!",
    ],
    "fricative_duration": [
        "Great sound! Can you hold it a little longer? Sssssssss — like that!",
        "Ooh you almost got it — just hold the ssss a tiny bit more!",
        "So good! Try stretching it out — sssssss — like a long snake sound.",
    ],
    "wrong_phoneme": [
        "Hmm I got confused! Let me show you — ssssss. Can you copy that?",
        "Almost! I need the hissy sound — ssssss — like air escaping a balloon.",
    ],
}

def _pick(category: str, advance: bool = False, level: str = "isolation") -> str:
    if category == "praise":
        bank = _TTS["praise_advance"] if advance else _TTS["praise"]
    elif category == "model_sound":
        key  = f"model_{level}" if f"model_{level}" in _TTS else "model_isolation"
        bank = _TTS[key]
    else:
        bank = _TTS.get(category, ["..."])
    return random.choice(bank)

def _hint_text(feature: str, fv: FeatureVector) -> str:
    bank = _HINTS.get(feature, _HINTS["wrong_phoneme"])
    return random.choice(bank)


# ── Smoke test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from stage2_features import FeatureVector

    def make_fv(score, centroid=6000, flatness=0.4, zcr=0.5, dur=0.13, quality=True, reason="ok"):
        """Make a fake FeatureVector with a given overall score for testing."""
        sub = {
            "spectral_centroid":  min(score + 0.1, 1.0),
            "spectral_flatness":  score,
            "zero_crossing_rate": score,
            "fricative_duration": score,
        }
        return FeatureVector(
            spectral_centroid=centroid,
            spectral_flatness=flatness,
            zero_crossing_rate=zcr,
            fricative_duration=dur,
            sub_scores=sub,
            phoneme_score=score,
            pitch_correct=centroid > 4000,
            duration_correct=0.07 < dur < 0.28,
            spectral_match=flatness,
            quality_ok=quality,
            quality_reason=reason,
        )

    def run(label, fv, state):
        d = decide(fv, state)
        print(f"\n  [{label}]")
        print(f"    score={fv.phoneme_score:.2f}  type={d.feedback_type}  advance={d.advance}  drop={d.drop_back}")
        print(f"    led={d.led_state}")
        print(f"    face={d.face_state}")
        print(f"    tts: \"{d.tts_text}\"")
        print(f"    hint={d.hint}  |  level now: {state.current_level}")

    print("=" * 60)
    print("Stage 3 — Feedback Decision Engine smoke test")
    print("=" * 60)

    # Test 1: 3 passes → advance
    print("\n-- Scenario: 3 consecutive passes → should advance --")
    s = SessionState(current_level="isolation")
    for i in range(3):
        run(f"pass #{i+1}", make_fv(0.82), s)

    # Test 2: 3 fails → drop back
    print("\n-- Scenario: 3 consecutive fails → should drop --")
    s2 = SessionState(current_level="syllable")
    for i in range(3):
        run(f"fail #{i+1}", make_fv(0.30, centroid=1800, quality=False, reason="fricative too short"), s2)

    # Test 3: corrective path — centroid is the problem
    print("\n-- Scenario: mid score, centroid is weak --")
    s3 = SessionState()
    fv_weak_centroid = make_fv(0.55, centroid=2500)
    fv_weak_centroid.sub_scores["spectral_centroid"] = 0.20
    fv_weak_centroid.pitch_correct = False
    run("weak centroid", fv_weak_centroid, s3)

    # Test 4: silent attempt
    print("\n-- Scenario: silent / no attempt --")
    s4 = SessionState()
    run("silent", make_fv(0.0, quality=False, reason="too quiet"), s4)

    # Test 5: mixed streak — no advance, no drop
    print("\n-- Scenario: pass-fail-pass (mixed, no streak) --")
    s5 = SessionState(current_level="word")
    for score, label in [(0.80, "pass"), (0.35, "fail"), (0.75, "pass")]:
        run(label, make_fv(score), s5)
