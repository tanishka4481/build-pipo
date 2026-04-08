"""
Stage 1 — Audio Preprocessor
==============================
Input  : raw WAV (base64 string OR filepath)
Output : PreprocessResult dataclass with:
           - audio_segment  : np.ndarray  (trimmed, normalized mono signal)
           - sample_rate    : int
           - fricative_mask : np.ndarray  (bool, frame-level — True = fricative region)
           - fricative_start: float       (seconds)
           - fricative_end  : float       (seconds)
           - fricative_duration: float    (seconds)
           - quality_ok     : bool        (False = too short / too quiet / no fricative found)
           - quality_reason : str         (human-readable why quality_ok is False)

Design notes
------------
For /s/ detection we use a two-pass approach:
  Pass 1 — VAD: strip leading/trailing silence using energy envelope (simple, fast)
  Pass 2 — Fricative detector: within the voiced window, find the high-frequency
            noise burst that characterises /s/ and /z/.
            /s/ lives mostly above 4 kHz — we split the spectrum and look for
            frames where HF energy > LF energy by a ratio threshold.

No ML, no external models. Pure signal processing.
"""

import base64
import io
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import librosa
import numpy as np
import soundfile as sf

warnings.filterwarnings("ignore", category=UserWarning)

# ── Tunable constants ──────────────────────────────────────────────────────────
SR_TARGET       = 16_000   # resample everything to 16 kHz
FRAME_LEN       = 512      # samples per frame  (~32 ms at 16k)
HOP_LEN         = 128      # hop size           (~8 ms at 16k)

# VAD (silence stripping)
VAD_TOP_DB      = 30       # librosa trim threshold — lower = keep more
VAD_MIN_DUR_S   = 0.05     # frames shorter than this after trim are discarded

# Fricative detector
FRIC_HF_HZ      = 4000     # boundary between LF and HF bands
FRIC_RATIO_THRESH = 1.4    # HF/LF energy ratio to call a frame "fricative"
FRIC_MIN_DUR_S  = 0.04     # minimum fricative burst length (seconds)
FRIC_MERGE_GAP  = 0.03     # merge fricative regions closer than this (seconds)

# Quality gates
MIN_TOTAL_DUR_S = 0.15     # whole clip must be at least this long
MAX_TOTAL_DUR_S = 4.0      # clip longer than this is probably noise / bad rec
MIN_FRIC_DUR_S  = 0.04     # at least 40 ms of fricative — /s/ is ~80–200 ms typically
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class PreprocessResult:
    audio_segment:       np.ndarray         # trimmed, normalised signal
    sample_rate:         int                = SR_TARGET
    fricative_mask:      np.ndarray         = field(default_factory=lambda: np.array([]))
    fricative_start:     float              = 0.0
    fricative_end:       float              = 0.0
    fricative_duration:  float              = 0.0
    quality_ok:          bool               = True
    quality_reason:      str                = "ok"

    # convenience ──────────────────────────────────────────────────────────────
    @property
    def fricative_audio(self) -> np.ndarray:
        """Return the raw audio samples that correspond to the fricative region."""
        start = int(self.fricative_start * self.sample_rate)
        end   = int(self.fricative_end   * self.sample_rate)
        return self.audio_segment[start:end]

    @property
    def total_duration(self) -> float:
        return len(self.audio_segment) / self.sample_rate


# ── Public entry point ─────────────────────────────────────────────────────────

def preprocess(source: Union[str, bytes, Path]) -> PreprocessResult:
    """
    Main entry point.

    source can be:
      - a filepath (str or Path)
      - raw WAV bytes
      - a base64-encoded WAV string (as the RPi will send)
    """
    audio, sr = _load(source)
    audio      = _normalize(audio)
    audio, ok, reason = _vad_trim(audio, sr)

    if not ok:
        return PreprocessResult(audio_segment=audio, quality_ok=False, quality_reason=reason)

    mask, f_start, f_end = _detect_fricative(audio, sr)
    f_dur = f_end - f_start

    # quality gates
    if f_dur < MIN_FRIC_DUR_S:
        return PreprocessResult(
            audio_segment=audio,
            fricative_mask=mask,
            fricative_start=f_start,
            fricative_end=f_end,
            fricative_duration=f_dur,
            quality_ok=False,
            quality_reason=f"fricative too short ({f_dur*1000:.0f} ms < {MIN_FRIC_DUR_S*1000:.0f} ms)"
        )

    return PreprocessResult(
        audio_segment=audio,
        sample_rate=SR_TARGET,
        fricative_mask=mask,
        fricative_start=f_start,
        fricative_end=f_end,
        fricative_duration=f_dur,
        quality_ok=True,
        quality_reason="ok",
    )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load(source: Union[str, bytes, Path]) -> tuple[np.ndarray, int]:
    """Load audio from filepath, raw bytes, or base64 string → (mono float32, sr)"""
    if isinstance(source, (str, Path)) and Path(source).exists():
        audio, sr = librosa.load(str(source), sr=SR_TARGET, mono=True)
    elif isinstance(source, bytes):
        audio, sr = sf.read(io.BytesIO(source), dtype="float32", always_2d=False)
        if sr != SR_TARGET:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=SR_TARGET)
        sr = SR_TARGET
    elif isinstance(source, str):
        # assume base64
        raw = base64.b64decode(source)
        audio, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
        if sr != SR_TARGET:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=SR_TARGET)
        sr = SR_TARGET
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")

    # force mono if stereo slipped through
    if audio.ndim == 2:
        audio = audio.mean(axis=1)

    return audio.astype(np.float32), sr


def _normalize(audio: np.ndarray) -> np.ndarray:
    """Peak normalize to [-1, 1]. Avoids division by near-zero."""
    peak = np.max(np.abs(audio))
    if peak < 1e-6:
        return audio
    return audio / peak


def _vad_trim(audio: np.ndarray, sr: int) -> tuple[np.ndarray, bool, str]:
    """
    Strip silence from start/end using librosa.effects.trim.
    Returns (trimmed_audio, quality_ok, reason).
    """
    total_dur = len(audio) / sr
    if total_dur < MIN_TOTAL_DUR_S:
        return audio, False, f"clip too short ({total_dur*1000:.0f} ms)"
    if total_dur > MAX_TOTAL_DUR_S:
        return audio, False, f"clip too long ({total_dur:.1f}s) — likely not a single phoneme attempt"

    trimmed, _ = librosa.effects.trim(audio, top_db=VAD_TOP_DB, frame_length=FRAME_LEN, hop_length=HOP_LEN)

    if len(trimmed) / sr < VAD_MIN_DUR_S:
        return audio, False, "too quiet after silence removal — mic issue or no attempt"

    return trimmed, True, "ok"


def _detect_fricative(audio: np.ndarray, sr: int) -> tuple[np.ndarray, float, float]:
    """
    Locate the fricative burst in the audio.

    Strategy:
      1. Compute STFT
      2. Split into LF (< FRIC_HF_HZ) and HF (>= FRIC_HF_HZ) bands
      3. Compute per-frame HF/LF energy ratio
      4. Threshold → boolean frame mask
      5. Find the longest contiguous True run (the main fricative)
      6. Merge small gaps, enforce minimum duration

    Returns (frame_mask, start_sec, end_sec)
    """
    stft        = np.abs(librosa.stft(audio, n_fft=FRAME_LEN*2, hop_length=HOP_LEN))
    freqs       = librosa.fft_frequencies(sr=sr, n_fft=FRAME_LEN*2)

    lf_mask     = freqs < FRIC_HF_HZ
    hf_mask     = freqs >= FRIC_HF_HZ

    lf_energy   = stft[lf_mask, :].mean(axis=0) + 1e-8
    hf_energy   = stft[hf_mask, :].mean(axis=0) + 1e-8

    ratio       = hf_energy / lf_energy
    fric_frames = ratio > FRIC_RATIO_THRESH

    # merge tiny gaps (< FRIC_MERGE_GAP seconds)
    gap_frames  = int(FRIC_MERGE_GAP * sr / HOP_LEN)
    fric_frames = _merge_gaps(fric_frames, gap_frames)

    # find the longest contiguous run
    start_frame, end_frame = _longest_run(fric_frames)

    # nothing found — leave mask empty, caller will catch via f_dur < MIN_FRIC_DUR_S
    # (no fallback: we'd rather fail honestly than score noise as a fricative)

    start_sec = librosa.frames_to_time(start_frame, sr=sr, hop_length=HOP_LEN)
    end_sec   = librosa.frames_to_time(end_frame,   sr=sr, hop_length=HOP_LEN)

    return fric_frames, float(start_sec), float(end_sec)


def _merge_gaps(mask: np.ndarray, gap: int) -> np.ndarray:
    """Fill runs of False that are shorter than `gap` frames."""
    m = mask.copy()
    i = 0
    while i < len(m):
        if not m[i]:
            j = i
            while j < len(m) and not m[j]:
                j += 1
            if (j - i) <= gap:
                m[i:j] = True
            i = j
        else:
            i += 1
    return m


def _longest_run(mask: np.ndarray) -> tuple[int, int]:
    """Return (start, end) frame indices of the longest True run."""
    best_start = best_end = best_len = 0
    cur_start = None
    for i, v in enumerate(mask):
        if v and cur_start is None:
            cur_start = i
        elif not v and cur_start is not None:
            run_len = i - cur_start
            if run_len > best_len:
                best_len, best_start, best_end = run_len, cur_start, i
            cur_start = None
    if cur_start is not None:
        run_len = len(mask) - cur_start
        if run_len > best_len:
            best_start, best_end = cur_start, len(mask)
    return best_start, best_end


def _butter_highpass(cutoff, sr, order=4):
    from scipy.signal import butter
    nyq = sr / 2
    return butter(order, cutoff / nyq, btype="high", analog=False)


# ── Quick smoke test (run directly) ──────────────────────────────────────────
if __name__ == "__main__":
    import sys

    print("=" * 56)
    print("Stage 1 — Preprocessor smoke test")
    print("=" * 56)

    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(f"\nLoading: {path}")
        result = preprocess(path)
    else:
        # generate a synthetic /s/-like signal: white noise burst (high freq) + silence
        print("\nNo file given — generating synthetic /s/ signal...")
        sr      = SR_TARGET
        silence = np.zeros(int(0.1 * sr), dtype=np.float32)
        # white noise bandpass-filtered above 4kHz to simulate /s/
        noise   = np.random.randn(int(0.15 * sr)).astype(np.float32) * 0.6
        b, a    = _butter_highpass(4000, sr)
        from scipy.signal import lfilter
        fric    = lfilter(b, a, noise).astype(np.float32)
        audio   = np.concatenate([silence, fric, silence])
        # write to bytes and pass as raw bytes
        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV", subtype="FLOAT")
        result = preprocess(buf.getvalue())

    print(f"\n  quality_ok        : {result.quality_ok}")
    print(f"  quality_reason    : {result.quality_reason}")
    print(f"  total_duration    : {result.total_duration*1000:.1f} ms")
    print(f"  fricative_start   : {result.fricative_start*1000:.1f} ms")
    print(f"  fricative_end     : {result.fricative_end*1000:.1f} ms")
    print(f"  fricative_duration: {result.fricative_duration*1000:.1f} ms")
    print(f"  fricative_audio   : {len(result.fricative_audio)} samples")
    print(f"  fricative_mask    : {result.fricative_mask.sum()} / {len(result.fricative_mask)} frames flagged")


