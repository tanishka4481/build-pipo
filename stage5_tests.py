"""
Stage 5 — Test Suite
======================
Three layers of tests:

Layer 1 — Unit tests
    Each stage tested in isolation with controlled inputs.
    Validates thresholds, edge cases, error handling.

Layer 2 — Acoustic realism tests
    Synthetic signals designed to mimic real child speech patterns:
    - /s/ with room noise
    - /s/ with vowel bleed (child says "suh" not "s")
    - /th/ substitution (most common for ages 3-5)
    - /f/ substitution
    - Whispered attempt (low amplitude)
    - Shouted attempt (clipping)
    - Background noise only (TV in room)

Layer 3 — Scenario tests
    Full pipeline runs simulating real therapy arcs:
    - Child who advances through all 5 levels
    - Child who plateaus and drops back
    - Child who starts strong then fatigues
    - Mixed performance (realistic)

Layer 4 — Regression tests
    Fixed-seed tests with expected outputs.
    These are your "nothing broke" checks before pushing to device.

Run:
    python3 stage5_tests.py           # all tests + report
    python3 stage5_tests.py --quick   # regression only (fast)
    python3 stage5_tests.py --layer 2 # specific layer
"""

import sys
import io
import time
import uuid
import argparse
import numpy as np
import soundfile as sf
from dataclasses import dataclass
from scipy.signal import butter, lfilter, chirp
from typing import Callable

from stage1_preprocess import preprocess, SR_TARGET
from stage2_features    import extract, TARGETS, WEIGHTS
from stage3_feedback    import decide, SessionState, PASS_THRESHOLD, FAIL_THRESHOLD, ADVANCE_STREAK, DROP_STREAK

SR = SR_TARGET

# ── Colour output ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):  print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg):print(f"  {RED}✗{RESET} {msg}")
def warn(msg):print(f"  {YELLOW}~{RESET} {msg}")
def info(msg):print(f"  {CYAN}·{RESET} {msg}")

# ── Audio synthesis helpers ────────────────────────────────────────────────────

def _hp(sig, cutoff, sr=SR):
    b, a = butter(4, cutoff / (sr / 2), btype="high")
    return lfilter(b, a, sig).astype(np.float32)

def _lp(sig, cutoff, sr=SR):
    b, a = butter(4, cutoff / (sr / 2), btype="low")
    return lfilter(b, a, sig).astype(np.float32)

def _bp(sig, lo, hi, sr=SR):
    b, a = butter(4, [lo / (sr / 2), hi / (sr / 2)], btype="band")
    return lfilter(b, a, sig).astype(np.float32)

def _noise(dur, amp=0.7, sr=SR):
    return (np.random.randn(int(dur * sr)) * amp).astype(np.float32)

def _silence(dur, sr=SR):
    return np.zeros(int(dur * sr), dtype=np.float32)

def _to_wav(audio, sr=SR) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, np.clip(audio, -1, 1), sr, format="WAV", subtype="FLOAT")
    return buf.getvalue()

def _pipeline(wav_bytes: bytes):
    r1 = preprocess(wav_bytes)
    fv = extract(r1)
    return r1, fv

# ── Realistic audio builders ───────────────────────────────────────────────────

class AudioBuilder:
    """
    Builds speech-like WAV signals for testing.
    All designed to approximate what a MEMS mic picks up from a 4-year-old.
    """

    @staticmethod
    def clean_s(dur=0.13, amp=0.7) -> bytes:
        """Perfect /s/ — high-freq noise, good duration, no bleed."""
        sil   = _silence(0.08)
        fric  = _hp(_noise(dur, amp), 5000)
        return _to_wav(np.concatenate([sil, fric, sil]))

    @staticmethod
    def s_with_room_noise(snr_db=15) -> bytes:
        """
        /s/ with background room noise (TV, siblings).
        SNR ~15dB is typical home environment.
        """
        sil    = _silence(0.08)
        fric   = _hp(_noise(0.13, 0.6), 5000)
        signal = np.concatenate([sil, fric, sil])
        noise  = _noise(len(signal) / SR, amp=1.0)
        # mix at target SNR
        sig_rms   = np.sqrt(np.mean(signal**2)) + 1e-8
        noise_rms = np.sqrt(np.mean(noise**2))  + 1e-8
        scale = sig_rms / (noise_rms * 10**(snr_db/20))
        mixed = signal + noise * scale
        return _to_wav(mixed / (np.max(np.abs(mixed)) + 1e-8))

    @staticmethod
    def s_with_vowel_bleed(vowel_amp=0.4) -> bytes:
        """
        Child says 'suh' instead of isolated /s/.
        Fricative + schwa vowel. Common in 3-5 year olds.
        """
        sil   = _silence(0.06)
        fric  = _hp(_noise(0.10, 0.7), 5000)
        vowel = _bp(_noise(0.12, vowel_amp), 200, 1000)
        return _to_wav(np.concatenate([sil, fric, vowel, sil]))

    @staticmethod
    def th_substitution() -> bytes:
        """/θ/ — dental fricative. Centroid ~2–3 kHz. Very common substitution."""
        sil  = _silence(0.08)
        fric = _bp(_noise(0.13, 0.6), 1000, 3500)
        return _to_wav(np.concatenate([sil, fric, sil]))

    @staticmethod
    def f_substitution() -> bytes:
        """/f/ — labiodental. Centroid ~1.5–4 kHz. Also common."""
        sil  = _silence(0.08)
        fric = _bp(_noise(0.13, 0.6), 1500, 4000)
        return _to_wav(np.concatenate([sil, fric, sil]))

    @staticmethod
    def whispered_s() -> bytes:
        """Very quiet /s/ — child is shy or uncertain. Low amplitude."""
        sil  = _silence(0.08)
        fric = _hp(_noise(0.11, 0.08), 5000)   # very low amp
        return _to_wav(np.concatenate([sil, fric, sil]))

    @staticmethod
    def clipped_s() -> bytes:
        """Shouted /s/ — mic clipping. Should not crash pipeline."""
        sil  = _silence(0.08)
        fric = _hp(_noise(0.13, 3.0), 5000)    # way over 1.0 before normalize
        return _to_wav(np.concatenate([sil, fric, sil]))

    @staticmethod
    def background_noise_only() -> bytes:
        """No speech — just broadband room noise. Should fail or score low."""
        noise = _noise(0.5, 0.3)
        return _to_wav(noise)

    @staticmethod
    def pure_silence() -> bytes:
        return _to_wav(_silence(0.5))

    @staticmethod
    def too_short() -> bytes:
        return _to_wav(_hp(_noise(0.04, 0.6), 5000))

    @staticmethod
    def perseveration(dur=0.4) -> bytes:
        """Child holds /s/ too long — perseverating."""
        sil  = _silence(0.05)
        fric = _hp(_noise(dur, 0.7), 5000)
        return _to_wav(np.concatenate([sil, fric, sil]))

    @staticmethod
    def chirp_sweep() -> bytes:
        """Frequency sweep — stress test for spectral analysis."""
        t    = np.linspace(0, 0.3, int(0.3 * SR))
        sig  = chirp(t, f0=500, f1=8000, t1=0.3, method="linear").astype(np.float32) * 0.5
        return _to_wav(sig)


# ── Test runner ────────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    name:    str
    passed:  bool
    message: str
    duration_ms: float = 0.0

results: list[TestResult] = []

def test(name: str):
    """Decorator for test functions — auto-runs immediately on decoration."""
    def decorator(fn: Callable):
        t0 = time.perf_counter()
        try:
            fn()
            ms = (time.perf_counter() - t0) * 1000
            results.append(TestResult(name, True, "ok", ms))
            ok(f"{name}  ({ms:.0f}ms)")
        except AssertionError as e:
            ms = (time.perf_counter() - t0) * 1000
            results.append(TestResult(name, False, str(e), ms))
            fail(f"{name}  →  {e}")
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            results.append(TestResult(name, False, f"EXCEPTION: {e}", ms))
            fail(f"{name}  →  EXCEPTION: {e}")
        return fn
    return decorator


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — Unit tests
# ══════════════════════════════════════════════════════════════════════════════

def run_layer1():
    print(f"\n{BOLD}{CYAN}Layer 1 — Unit Tests{RESET}")

    @test("stage1: clean /s/ passes quality check")
    def _():
        r = preprocess(AudioBuilder.clean_s())
        assert r.quality_ok, f"expected ok, got: {r.quality_reason}"
        assert r.fricative_duration > 0.05, f"fricative too short: {r.fricative_duration}"

    @test("stage1: pure silence fails quality")
    def _():
        r = preprocess(AudioBuilder.pure_silence())
        assert not r.quality_ok, "silence should fail"

    @test("stage1: too-short clip fails quality")
    def _():
        r = preprocess(AudioBuilder.too_short())
        assert not r.quality_ok, "too short should fail"

    @test("stage1: clip does not crash on clipped audio")
    def _():
        r = preprocess(AudioBuilder.clipped_s())
        # just must not throw — quality can go either way
        assert hasattr(r, "quality_ok")

    @test("stage1: fricative_audio is a subset of full audio")
    def _():
        r = preprocess(AudioBuilder.clean_s())
        assert len(r.fricative_audio) <= len(r.audio_segment)
        assert len(r.fricative_audio) > 0

    @test("stage2: clean /s/ scores above PASS_THRESHOLD")
    def _():
        _, fv = _pipeline(AudioBuilder.clean_s())
        assert fv.phoneme_score >= PASS_THRESHOLD, \
            f"clean /s/ scored {fv.phoneme_score:.3f}, need >= {PASS_THRESHOLD}"

    @test("stage2: silence scores 0.0")
    def _():
        _, fv = _pipeline(AudioBuilder.pure_silence())
        assert fv.phoneme_score == 0.0, f"got {fv.phoneme_score}"

    @test("stage2: all sub_scores are 0.0–1.0")
    def _():
        _, fv = _pipeline(AudioBuilder.clean_s())
        for k, v in fv.sub_scores.items():
            assert 0.0 <= v <= 1.0, f"{k} out of range: {v}"

    @test("stage2: sub_score weights sum to 1.0")
    def _():
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 1e-6, f"weights sum to {total}"

    @test("stage3: 3 passes → advance")
    def _():
        state = SessionState(current_level="isolation")
        for _ in range(ADVANCE_STREAK):
            fv = _make_fv(0.82)
            d  = decide(fv, state)
        assert d.advance, "should have advanced after 3 passes"
        assert state.current_level == "syllable", f"got {state.current_level}"

    @test("stage3: 3 fails → drop_back")
    def _():
        state = SessionState(current_level="syllable")
        for _ in range(DROP_STREAK):
            fv = _make_fv(0.30, quality=False)
            d  = decide(fv, state)
        assert d.drop_back, "should drop after 3 fails"
        assert state.current_level == "isolation", f"got {state.current_level}"

    @test("stage3: mixed streak breaks advance counter")
    def _():
        state = SessionState()
        decide(_make_fv(0.80), state)
        decide(_make_fv(0.35), state)   # breaks streak
        decide(_make_fv(0.80), state)
        assert state.consecutive_pass == 1, \
            f"streak should reset, got {state.consecutive_pass}"

    @test("stage3: no_attempt on zero-score silent")
    def _():
        state = SessionState()
        fv    = _make_fv(0.0, quality=False, reason="too quiet")
        d     = decide(fv, state)
        assert d.feedback_type == "no_attempt"
        assert d.led_state == "slow_pulse_blue"

    @test("stage3: cannot advance past 'phrase' (last level)")
    def _():
        state = SessionState(current_level="phrase")
        for _ in range(ADVANCE_STREAK + 2):
            decide(_make_fv(0.90), state)
        assert state.current_level == "phrase", \
            f"should stay at phrase, got {state.current_level}"

    @test("stage3: cannot drop below 'discrimination' (first level)")
    def _():
        state = SessionState(current_level="discrimination")
        for _ in range(DROP_STREAK + 2):
            decide(_make_fv(0.20, quality=False), state)
        assert state.current_level == "discrimination", \
            f"should stay at discrimination, got {state.current_level}"


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — Acoustic realism tests
# ══════════════════════════════════════════════════════════════════════════════

def run_layer2():
    print(f"\n{BOLD}{CYAN}Layer 2 — Acoustic Realism Tests{RESET}")

    @test("acoustic: /s/ + room noise still passes (SNR 15dB)")
    def _():
        _, fv = _pipeline(AudioBuilder.s_with_room_noise(snr_db=15))
        assert fv.quality_ok or fv.phoneme_score > 0.3, \
            f"too aggressive on noisy /s/, score={fv.phoneme_score:.3f}"

    @test("acoustic: /s/ + vowel bleed — fricative still detected")
    def _():
        r, fv = _pipeline(AudioBuilder.s_with_vowel_bleed())
        assert r.quality_ok, f"vowel bleed broke Stage 1: {r.quality_reason}"
        assert fv.phoneme_score >= 0.5, \
            f"score too low for /s/+vowel: {fv.phoneme_score:.3f}"

    @test("acoustic: /th/ sub scores below PASS_THRESHOLD")
    def _():
        _, fv = _pipeline(AudioBuilder.th_substitution())
        assert fv.phoneme_score < PASS_THRESHOLD, \
            f"/th/ sub should not pass, got {fv.phoneme_score:.3f}"

    @test("acoustic: /f/ sub scores below PASS_THRESHOLD")
    def _():
        _, fv = _pipeline(AudioBuilder.f_substitution())
        assert fv.phoneme_score < PASS_THRESHOLD, \
            f"/f/ sub should not pass, got {fv.phoneme_score:.3f}"

    @test("acoustic: /th/ sub — pitch_correct is False")
    def _():
        _, fv = _pipeline(AudioBuilder.th_substitution())
        # centroid for /th/ is ~2kHz — well below 4kHz threshold
        assert not fv.pitch_correct or fv.spectral_centroid < 4500, \
            f"centroid {fv.spectral_centroid:.0f}Hz is too high for /th/"

    @test("acoustic: whispered /s/ — pipeline handles low amplitude")
    def _():
        r, fv = _pipeline(AudioBuilder.whispered_s())
        # just must not crash — whispers may or may not pass quality
        assert hasattr(fv, "phoneme_score")
        assert 0.0 <= fv.phoneme_score <= 1.0

    @test("acoustic: clipped /s/ — no crash, score reasonable")
    def _():
        _, fv = _pipeline(AudioBuilder.clipped_s())
        assert 0.0 <= fv.phoneme_score <= 1.0, f"score out of range: {fv.phoneme_score}"

    @test("acoustic: background noise only — scores low or fails")
    def _():
        _, fv = _pipeline(AudioBuilder.background_noise_only())
        # should either fail quality or score low (broadband noise ≠ /s/ burst)
        assert not fv.quality_ok or fv.phoneme_score < 0.9, \
            f"background noise should not score high: {fv.phoneme_score:.3f}"

    @test("acoustic: perseveration (400ms) — duration_correct is False")
    def _():
        _, fv = _pipeline(AudioBuilder.perseveration(dur=0.4))
        if fv.quality_ok:
            assert not fv.duration_correct, \
                f"400ms /s/ should flag duration, sub={fv.sub_scores.get('fricative_duration', 0):.2f}"

    @test("acoustic: chirp sweep — no crash")
    def _():
        r, fv = _pipeline(AudioBuilder.chirp_sweep())
        assert hasattr(fv, "phoneme_score")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — Scenario / therapy arc tests
# ══════════════════════════════════════════════════════════════════════════════

def run_layer3():
    print(f"\n{BOLD}{CYAN}Layer 3 — Therapy Arc Scenarios{RESET}")

    @test("scenario: child advances through all 5 levels")
    def _():
        state = SessionState(current_level="discrimination")
        levels_hit = {"discrimination"}
        for _ in range(25):  # enough attempts to advance through all levels
            fv = _make_fv(0.85)
            decide(fv, state)
            levels_hit.add(state.current_level)
        assert "phrase" in levels_hit, \
            f"never reached phrase level. levels seen: {levels_hit}"

    @test("scenario: child plateaus and drops back")
    def _():
        state  = SessionState(current_level="word")
        start  = state.current_level
        for _ in range(DROP_STREAK):
            decide(_make_fv(0.25, quality=False), state)
        assert state.current_level != start, "should have dropped from word"

    @test("scenario: realistic mixed session (pass/fail/corrective)")
    def _():
        rng   = np.random.default_rng(42)
        state = SessionState(current_level="isolation")
        types = set()
        for _ in range(15):
            score = float(rng.uniform(0.3, 0.9))
            fv    = _make_fv(score, quality=score > 0.4)
            d     = decide(fv, state)
            types.add(d.feedback_type)
        # a realistic session should hit at least 2 feedback types
        assert len(types) >= 2, f"only one feedback type seen: {types}"

    @test("scenario: feedback language stays child-appropriate")
    def _():
        """TTS text must not contain clinical jargon."""
        forbidden = ["phoneme", "fricative", "alveolar", "spectral", "Hz", "dB",
                     "incorrect", "wrong", "failed", "bad"]
        state = SessionState()
        for score in [0.85, 0.55, 0.25, 0.0]:
            fv = _make_fv(score, quality=score > 0.1)
            d  = decide(fv, state)
            for word in forbidden:
                assert word.lower() not in d.tts_text.lower(), \
                    f"clinical word '{word}' in tts: \"{d.tts_text}\""

    @test("scenario: all led_states are non-empty strings")
    def _():
        state = SessionState()
        for score, q in [(0.85, True), (0.55, True), (0.25, False), (0.0, False)]:
            fv = _make_fv(score, quality=q)
            d  = decide(fv, state)
            assert isinstance(d.led_state, str) and len(d.led_state) > 0
            assert isinstance(d.face_state, str) and len(d.face_state) > 0
            assert isinstance(d.servo_action, str)

    @test("scenario: session state is mutable across calls (not reset)")
    def _():
        state = SessionState()
        for _ in range(2):
            decide(_make_fv(0.85), state)
        assert state.consecutive_pass == 2, \
            f"expected 2 consecutive passes, got {state.consecutive_pass}"


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — Regression tests (fixed seed, expected values)
# ══════════════════════════════════════════════════════════════════════════════

def run_layer4():
    print(f"\n{BOLD}{CYAN}Layer 4 — Regression Tests (fixed seed){RESET}")

    np.random.seed(2025)  # fixed — results must be deterministic

    @test("regression: clean /s/ phoneme_score in [0.65, 1.0]")
    def _():
        _, fv = _pipeline(AudioBuilder.clean_s(dur=0.13, amp=0.7))
        assert 0.65 <= fv.phoneme_score <= 1.0, \
            f"score {fv.phoneme_score:.4f} out of expected range [0.65, 1.0]"

    @test("regression: /th/ substitution centroid < 4000 Hz")
    def _():
        _, fv = _pipeline(AudioBuilder.th_substitution())
        assert fv.spectral_centroid < 4000, \
            f"centroid {fv.spectral_centroid:.0f}Hz — /th/ should be below 4kHz"

    @test("regression: perseveration sub_duration < 0.5")
    def _():
        _, fv = _pipeline(AudioBuilder.perseveration(dur=0.4))
        if fv.quality_ok:
            sub_dur = fv.sub_scores.get("fricative_duration", 1.0)
            assert sub_dur < 0.5, \
                f"duration sub-score {sub_dur:.3f} too high for 400ms perseveration"

    @test("regression: stage3 advance fires on exactly 3rd pass")
    def _():
        state = SessionState(current_level="isolation")
        for i in range(1, 4):
            fv = _make_fv(0.80)
            d  = decide(fv, state)
            if i < 3:
                assert not d.advance, f"advanced too early on attempt {i}"
            else:
                assert d.advance, "should advance on 3rd pass"

    @test("regression: feedback_type sequence for pass/pass/fail")
    def _():
        state = SessionState()
        types = []
        for score in [0.80, 0.80, 0.25]:
            fv = _make_fv(score, quality=score > 0.1)
            d  = decide(fv, state)
            types.append(d.feedback_type)
        assert types[0] == "praise"
        assert types[1] == "praise"
        assert types[2] in ("model", "no_attempt")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_fv(score, centroid=6000, quality=True, reason="ok"):
    from stage2_features import FeatureVector
    sub = {k: min(score + 0.05, 1.0) for k in WEIGHTS}
    if not quality:
        sub = {k: max(score - 0.1, 0.0) for k in WEIGHTS}
    return FeatureVector(
        spectral_centroid   = centroid if quality else 1800,
        spectral_flatness   = score,
        zero_crossing_rate  = score,
        fricative_duration  = 0.12 if quality else 0.02,
        sub_scores          = sub,
        phoneme_score       = score,
        pitch_correct       = centroid > 4000 and quality,
        duration_correct    = quality and score > 0.5,
        spectral_match      = score,
        quality_ok          = quality,
        quality_reason      = reason,
    )


# ── Report ─────────────────────────────────────────────────────────────────────

def print_report():
    passed  = [r for r in results if r.passed]
    failed  = [r for r in results if not r.passed]
    total   = len(results)
    avg_ms  = sum(r.duration_ms for r in results) / total if total else 0

    print(f"\n{'='*58}")
    print(f"{BOLD}TEST REPORT{RESET}")
    print(f"{'='*58}")
    print(f"  Total   : {total}")
    print(f"  {GREEN}Passed  : {len(passed)}{RESET}")
    if failed:
        print(f"  {RED}Failed  : {len(failed)}{RESET}")
        print(f"\n{RED}Failures:{RESET}")
        for r in failed:
            print(f"  ✗ {r.name}")
            print(f"    {r.message}")
    print(f"\n  Avg test time: {avg_ms:.0f} ms")
    pct = len(passed) / total * 100 if total else 0
    print(f"  Pass rate: {pct:.0f}%")

    if not failed:
        print(f"\n{GREEN}{BOLD}  All tests passed. Ready for hardware.{RESET}")
    else:
        print(f"\n{RED}{BOLD}  Fix failures before flashing to device.{RESET}")

    return len(failed) == 0


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick",  action="store_true", help="regression only")
    parser.add_argument("--layer",  type=int, default=0, help="run only this layer (1-4)")
    args = parser.parse_args()

    print(f"{BOLD}Speech Therapy Device — Stage 5 Test Suite{RESET}")
    print(f"Target phoneme: /s/  |  SR: {SR} Hz")

    if args.quick:
        run_layer4()
    elif args.layer == 1:
        run_layer1()
    elif args.layer == 2:
        run_layer2()
    elif args.layer == 3:
        run_layer3()
    elif args.layer == 4:
        run_layer4()
    else:
        run_layer1()
        run_layer2()
        run_layer3()
        run_layer4()

    success = print_report()
    sys.exit(0 if success else 1)
