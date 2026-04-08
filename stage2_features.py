"""
Stage 2 — Feature Extractor
=============================
Input  : PreprocessResult from Stage 1
Output : FeatureVector dataclass with:

    spectral_centroid   float   Hz   — centre of mass of the spectrum
                                       /s/ should be > 4500 Hz
                                       /r/ would be < 2500 Hz
                                       low centroid = vowel bleed or no attempt

    spectral_flatness   float   0-1  — how noise-like vs tonal the signal is
                                       pure /s/ = white-noise-like → high flatness (> 0.3)
                                       vowel / humming = tonal → low flatness

    zero_crossing_rate  float   0-1  — normalised ZCR
                                       fricatives have very high ZCR (rapidly oscillating noise)
                                       voiced sounds have low ZCR

    fricative_duration  float   s    — length of the fricative burst
                                       target: 0.08–0.25 s for a good /s/
                                       too short = insufficient breath support
                                       too long = might be perseverating or background noise

    sub_scores dict — each feature independently scored 0-1 against /s/ targets
    (these go straight into Stage 3 scorer AND into the DB for diagnostic logging)

Why these 4 features for /s/:
    /s/ is a high-frequency, aperiodic (noise-like) fricative.
    - High centroid    → energy above 4–5 kHz ✓
    - High flatness    → noise-like, not tonal ✓
    - High ZCR         → rapid sign changes in the waveform ✓
    - Right duration   → not a slip of the tongue, not forever ✓

All four must be present. A child humming "ssss" with no real airflow will have
low centroid + low flatness — caught immediately. A /th/ substitution will have
low centroid — also caught.
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import librosa

from stage1_preprocess import PreprocessResult, SR_TARGET


# ── /s/ phoneme targets & scoring windows ─────────────────────────────────────
#
# Each feature has:
#   IDEAL  — the value a clear adult /s/ would produce
#   OK_LO  — minimum acceptable (score starts dropping below this)
#   OK_HI  — max acceptable (flatness/ZCR have a ceiling too)
#   FAIL   — score = 0 at or beyond this
#
# Scoring is piecewise linear between these breakpoints.
# These are calibrated for children 3-5 (slightly lower centroid than adult norms).

TARGETS = {
    "spectral_centroid": {   # Hz
        "ideal":  6500,
        "ok_lo":  4000,   # below here = score < 1.0
        "fail_lo": 1500,  # below here = score 0
        "ok_hi":  9000,   # above here we don't penalise
    },
    "spectral_flatness": {   # 0–1
        "ideal":  0.55,
        "ok_lo":  0.25,
        "fail_lo": 0.05,
        "ok_hi":  1.0,
    },
    "zero_crossing_rate": {  # normalised 0–1
        "ideal":  0.35,
        "ok_lo":  0.18,
        "fail_lo": 0.05,
        "ok_hi":  1.0,
    },
    "fricative_duration": {  # seconds
        "ideal":  0.12,
        "ok_lo":  0.07,
        "fail_lo": 0.03,
        "ok_hi":  0.28,   # above here = penalise (too long)
        "fail_hi": 0.45,
    },
}

# How much each sub-score contributes to the final phoneme score
# (used by Stage 3, but defined here so the feature module owns the /s/ spec)
WEIGHTS = {
    "spectral_centroid":  0.40,   # most diagnostic for /s/ vs substitutions
    "spectral_flatness":  0.25,   # noise character
    "zero_crossing_rate": 0.20,   # high-freq oscillation
    "fricative_duration": 0.15,   # breath support proxy
}

FRAME_LEN  = 512
HOP_LEN    = 128


# ── Output dataclass ───────────────────────────────────────────────────────────

@dataclass
class FeatureVector:
    # raw features
    spectral_centroid:   float   # Hz
    spectral_flatness:   float   # 0–1
    zero_crossing_rate:  float   # 0–1 normalised
    fricative_duration:  float   # seconds

    # per-feature 0–1 scores
    sub_scores: dict = field(default_factory=dict)

    # weighted composite — filled in by extract()
    phoneme_score: float = 0.0

    # diagnostic flags for DB logging
    pitch_correct:    bool  = False   # centroid in target range
    duration_correct: bool  = False   # duration in target range
    spectral_match:   float = 0.0     # flatness sub-score (0–1)

    # pass-through from Stage 1 for convenience
    quality_ok:     bool = True
    quality_reason: str  = "ok"

    def summary(self) -> str:
        lines = [
            f"  phoneme_score      : {self.phoneme_score:.3f}",
            f"  spectral_centroid  : {self.spectral_centroid:.0f} Hz  (sub={self.sub_scores.get('spectral_centroid',0):.2f})",
            f"  spectral_flatness  : {self.spectral_flatness:.3f}     (sub={self.sub_scores.get('spectral_flatness',0):.2f})",
            f"  zero_crossing_rate : {self.zero_crossing_rate:.3f}     (sub={self.sub_scores.get('zero_crossing_rate',0):.2f})",
            f"  fricative_duration : {self.fricative_duration*1000:.0f} ms   (sub={self.sub_scores.get('fricative_duration',0):.2f})",
            f"  pitch_correct      : {self.pitch_correct}",
            f"  duration_correct   : {self.duration_correct}",
            f"  spectral_match     : {self.spectral_match:.3f}",
        ]
        return "\n".join(lines)


# ── Public entry point ─────────────────────────────────────────────────────────

def extract(result: PreprocessResult) -> FeatureVector:
    """
    Extract features from a PreprocessResult.
    If quality_ok is False, returns a zeroed FeatureVector with the same flags.
    """
    if not result.quality_ok:
        full_rms = float(np.sqrt(np.mean(result.audio_segment ** 2)))
        if full_rms < 0.01 or len(result.audio_segment) < 512:
            return FeatureVector(
                spectral_centroid=0.0, spectral_flatness=0.0,
                zero_crossing_rate=0.0, fricative_duration=0.0,
                phoneme_score=0.0, quality_ok=False,
                quality_reason=result.quality_reason,
            )
        # audio exists but no clean fricative — score from full clip, penalise duration
        audio_fb  = result.audio_segment
        sr_fb     = result.sample_rate
        centroid  = _spectral_centroid(audio_fb, sr_fb)
        flatness  = _spectral_flatness(audio_fb)
        zcr       = _zero_crossing_rate(audio_fb)
        raw_fb = {
            "spectral_centroid":  centroid,
            "spectral_flatness":  flatness,
            "zero_crossing_rate": zcr,
            "fricative_duration": 0.03,   # hard-penalise — no clear burst found
        }
        sub_fb    = {k: _score_feature(k, v) for k, v in raw_fb.items()}
        score_fb  = sum(sub_fb[k] * WEIGHTS[k] for k in WEIGHTS)
        return FeatureVector(
            spectral_centroid=centroid, spectral_flatness=flatness,
            zero_crossing_rate=zcr, fricative_duration=0.03,
            sub_scores=sub_fb, phoneme_score=round(float(score_fb), 4),
            pitch_correct=sub_fb["spectral_centroid"] >= 0.6,
            duration_correct=False, spectral_match=sub_fb["spectral_flatness"],
            quality_ok=False, quality_reason=result.quality_reason,
        )

    audio = result.fricative_audio
    sr    = result.sample_rate

    # guard: if fricative slice is too short for an STFT frame, use full clip
    if len(audio) < FRAME_LEN:
        audio = result.audio_segment

    centroid  = _spectral_centroid(audio, sr)
    flatness  = _spectral_flatness(audio)
    zcr       = _zero_crossing_rate(audio)
    duration  = result.fricative_duration

    raw = {
        "spectral_centroid":  centroid,
        "spectral_flatness":  flatness,
        "zero_crossing_rate": zcr,
        "fricative_duration": duration,
    }

    sub_scores    = {k: _score_feature(k, v) for k, v in raw.items()}
    phoneme_score = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)

    fv = FeatureVector(
        spectral_centroid   = centroid,
        spectral_flatness   = flatness,
        zero_crossing_rate  = zcr,
        fricative_duration  = duration,
        sub_scores          = sub_scores,
        phoneme_score       = round(float(phoneme_score), 4),
        pitch_correct       = sub_scores["spectral_centroid"] >= 0.6,
        duration_correct    = sub_scores["fricative_duration"] >= 0.6,
        spectral_match      = sub_scores["spectral_flatness"],
        quality_ok          = True,
        quality_reason      = "ok",
    )
    return fv


# ── Feature computations ───────────────────────────────────────────────────────

def _spectral_centroid(audio: np.ndarray, sr: int) -> float:
    """
    Median spectral centroid across frames (Hz).
    Using median instead of mean makes it robust to click artifacts.
    """
    stft  = np.abs(librosa.stft(audio, n_fft=FRAME_LEN * 2, hop_length=HOP_LEN))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=FRAME_LEN * 2)

    # centroid per frame: weighted mean of frequencies
    power      = stft ** 2
    total_pow  = power.sum(axis=0) + 1e-8
    centroids  = (freqs[:, None] * power).sum(axis=0) / total_pow

    return float(np.median(centroids))


def _spectral_flatness(audio: np.ndarray) -> float:
    """
    Spectral flatness (Wiener entropy) — geometric mean / arithmetic mean of spectrum.
    1.0 = pure white noise, 0.0 = pure sine wave.
    Returns the median across frames.
    """
    stft    = np.abs(librosa.stft(audio, n_fft=FRAME_LEN * 2, hop_length=HOP_LEN)) + 1e-8
    log_geo = np.log(stft).mean(axis=0)           # log geometric mean per frame
    arith   = stft.mean(axis=0)                    # arithmetic mean per frame
    flatness = np.exp(log_geo) / arith             # ratio
    return float(np.clip(np.median(flatness), 0.0, 1.0))


def _zero_crossing_rate(audio: np.ndarray) -> float:
    """
    Normalised ZCR (crossings per sample, 0–1 scaled to roughly [0, 0.5]).
    Returns the 75th percentile across frames (robust to quiet frames).
    """
    zcr_frames = librosa.feature.zero_crossing_rate(
        audio, frame_length=FRAME_LEN, hop_length=HOP_LEN
    )[0]
    # zcr is in crossings/sample, typically 0–0.5 for speech
    # normalise to 0–1 by dividing by 0.5
    normalised = np.clip(zcr_frames / 0.5, 0.0, 1.0)
    return float(np.percentile(normalised, 75))


# ── Scoring logic ──────────────────────────────────────────────────────────────

def _score_feature(name: str, value: float) -> float:
    """
    Piecewise-linear scoring. Returns 0–1.

    For centroid, flatness, ZCR:
        fail_lo → ok_lo  : 0.0 → 1.0  (linear ramp up)
        ok_lo   → ideal  : 1.0         (plateau)
        ideal   → ok_hi  : 1.0         (plateau continues)

    For duration (has both low AND high penalties):
        fail_lo → ok_lo  : 0.0 → 1.0
        ok_lo   → ideal  : 1.0
        ideal   → ok_hi  : 1.0
        ok_hi   → fail_hi: 1.0 → 0.0  (ramp down for too-long)
    """
    t = TARGETS[name]
    v = float(value)

    # low-end ramp
    if v <= t["fail_lo"]:
        return 0.0
    if v <= t["ok_lo"]:
        return (v - t["fail_lo"]) / (t["ok_lo"] - t["fail_lo"])

    # high-end penalty (duration only)
    if "fail_hi" in t:
        if v >= t["fail_hi"]:
            return 0.0
        if v >= t["ok_hi"]:
            return 1.0 - (v - t["ok_hi"]) / (t["fail_hi"] - t["ok_hi"])

    return 1.0


# ── Smoke test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import io
    import soundfile as sf
    from scipy.signal import butter, lfilter
    from stage1_preprocess import preprocess

    def make_audio(fric_freq_lo=4000, dur=0.13, add_vowel=False, silent=False, sr=SR_TARGET):
        sil  = np.zeros(int(0.10 * sr), dtype=np.float32)
        if silent:
            return np.concatenate([sil, sil, sil])
        noise = np.random.randn(int(dur * sr)).astype(np.float32) * 0.7
        b, a  = butter(4, fric_freq_lo / (sr / 2), btype="high")
        fric  = lfilter(b, a, noise).astype(np.float32)
        if add_vowel:
            b2, a2 = butter(4, 400 / (sr / 2), btype="low")
            vowel  = lfilter(b2, a2, np.random.randn(int(0.15 * sr)).astype(np.float32) * 0.5)
            return np.concatenate([sil, fric, vowel.astype(np.float32), sil])
        return np.concatenate([sil, fric, sil])

    def run(label, **kwargs):
        audio = make_audio(**kwargs)
        buf   = io.BytesIO()
        sf.write(buf, audio, SR_TARGET, format="WAV", subtype="FLOAT")
        r1 = preprocess(buf.getvalue())
        fv = extract(r1)
        print(f"\n[{label}]")
        if not fv.quality_ok:
            print(f"  FAILED quality: {fv.quality_reason}")
        else:
            print(fv.summary())

    print("=" * 56)
    print("Stage 2 — Feature Extractor smoke test")
    print("=" * 56)

    run("perfect /s/ (4kHz+ noise, 130ms)",    fric_freq_lo=4000,  dur=0.13)
    run("/s/ + vowel bleed",                    fric_freq_lo=4000,  dur=0.12, add_vowel=True)
    run("weak /s/ (2kHz noise = too low)",      fric_freq_lo=2000,  dur=0.13)
    run("very short /s/ (45ms)",                fric_freq_lo=4500,  dur=0.045)
    run("very long /s/ (400ms perseveration)",  fric_freq_lo=5000,  dur=0.40)
    run("silent attempt",                        silent=True)
