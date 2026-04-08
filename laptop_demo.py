"""
Laptop Demo — Speech Therapy Device
======================================
Runs the full ML pipeline on your laptop using:
  - Laptop mic (sounddevice)
  - Terminal UI (rich) — simulates LED ring, OLED face, scores
  - FastAPI server (stage4_server) running locally
  - SQLite DB auto-created

Usage:
  # Terminal 1 — start the server
  python3 stage4_server.py

  # Terminal 2 — run the demo
  python3 laptop_demo.py

  # Or run everything in one shot:
  python3 laptop_demo.py --selfhost

Controls (during demo):
  SPACE / Enter  — record a 2-second attempt
  q              — quit and show session summary
  s              — show current session stats
  r              — reset session (new child)

Install deps first:
  pip install sounddevice rich requests numpy soundfile scipy librosa
  (on Mac: brew install portaudio first)
  (on Ubuntu: sudo apt install portaudio19-dev)
"""

import io
import sys
import time
import uuid
import base64
import argparse
import threading
import subprocess
import numpy as np
import soundfile as sf
import requests

try:
    import sounddevice as sd
    MIC_AVAILABLE = True
except Exception:
    MIC_AVAILABLE = False

from rich.console import Console
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text
from rich.live    import Live
from rich.layout  import Layout
from rich.align   import Align
from rich         import box

console = Console()

# ── Config ─────────────────────────────────────────────────────────────────────
SR           = 16000
REC_SECONDS  = 2.0       # how long each attempt records
SERVER       = "http://localhost:8000"
CHILD_ID     = "demo_child_01"

# ── State ──────────────────────────────────────────────────────────────────────
session_id    = None
attempt_num   = 0
current_level = "isolation"
history       = []   # list of dicts from /attempt response


# ── LED ring simulation ────────────────────────────────────────────────────────
LED_FRAMES = {
    "slow_pulse_blue":    ("●", "blue",    "Waiting..."),
    "warm_pulse_white":   ("●", "white",   "Child detected"),
    "burst_green":        ("★", "green",   "Great attempt!"),
    "rainbow_spin":       ("★", "magenta", "LEVEL UP!"),
    "breathe_yellow":     ("◐", "yellow",  "Almost there"),
    "slow_red_pulse":     ("○", "red",     "Try again"),
    "soft_cyan_ripple":   ("~", "cyan",    "Listen to me..."),
    "waiting_blink":      ("·", "blue",    "Waiting for attempt"),
    "celebrate_bounce":   ("★", "magenta", "Amazing!"),
}

FACE_FRAMES = {
    "big_happy":          "^‿^",
    "celebrate_bounce":   "\\(^o^)/",
    "curious_tilt":       "(•ᴗ•)?",
    "waiting_blink":      "(-_-) zzz",
    "sad_then_model":     "(>_<)",
    "confused_tilt":      "(°_°)?",
    "slow_red_pulse":     "(•︵•)",
}


def render_led(led_state: str) -> Text:
    sym, colour, label = LED_FRAMES.get(led_state, ("?", "white", led_state))
    ring = " ".join([sym] * 12)
    t = Text()
    t.append(f"  {ring}\n", style=f"bold {colour}")
    t.append(f"  {label}", style=colour)
    return t


def render_face(face_state: str) -> Text:
    face = FACE_FRAMES.get(face_state, "(•_•)")
    return Text(f"\n  {face}\n", style="bold cyan", justify="center")


def render_score_bar(score: float) -> Text:
    filled  = int(score * 20)
    empty   = 20 - filled
    colour  = "green" if score >= 0.70 else "yellow" if score >= 0.45 else "red"
    bar     = "█" * filled + "░" * empty
    t = Text()
    t.append(f"  [{bar}] ", style=colour)
    t.append(f"{score:.2f}", style=f"bold {colour}")
    return t


def render_sub_scores(sub_scores: dict) -> str:
    lines = []
    labels = {
        "spectral_centroid":  "Pitch placement ",
        "spectral_flatness":  "Breath quality  ",
        "zero_crossing_rate": "Fricative crisp ",
        "fricative_duration": "Duration        ",
    }
    for k, label in labels.items():
        v = sub_scores.get(k, 0.0)
        bar = "▪" * int(v * 10) + "·" * (10 - int(v * 10))
        colour = "green" if v >= 0.6 else "yellow" if v >= 0.35 else "red"
        lines.append(f"  [grey50]{label}[/] [{colour}]{bar}[/] [{colour}]{v:.2f}[/]")
    return "\n".join(lines)


# ── Recording ──────────────────────────────────────────────────────────────────

def record_attempt() -> bytes:
    """Record REC_SECONDS of audio from mic, return as WAV bytes."""
    if not MIC_AVAILABLE:
        return _synthetic_attempt()

    console.print(f"\n[bold yellow]  ● Recording for {REC_SECONDS:.0f}s... speak now![/]")
    audio = sd.rec(
        int(REC_SECONDS * SR),
        samplerate=SR,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    audio = audio.flatten()
    buf = io.BytesIO()
    sf.write(buf, audio, SR, format="WAV", subtype="FLOAT")
    return buf.getvalue()


def _synthetic_attempt() -> bytes:
    """Generate a realistic synthetic /s/ attempt when no mic is available."""
    from scipy.signal import butter, lfilter
    console.print("[yellow]  (no mic — using synthetic /s/ audio)[/]")
    sil   = np.zeros(int(0.08 * SR), dtype=np.float32)
    noise = np.random.randn(int(0.13 * SR)).astype(np.float32) * 0.7
    b, a  = butter(4, 5000 / (SR / 2), btype="high")
    fric  = lfilter(b, a, noise).astype(np.float32)
    audio = np.concatenate([sil, fric, sil])
    buf   = io.BytesIO()
    sf.write(buf, audio, SR, format="WAV", subtype="FLOAT")
    return buf.getvalue()


# ── API calls ──────────────────────────────────────────────────────────────────

def start_session() -> str:
    r = requests.post(f"{SERVER}/session/start", json={
        "child_id":       CHILD_ID,
        "level":          "isolation",
        "target_phoneme": "s",
    }, timeout=5)
    r.raise_for_status()
    return r.json()["session_id"]


def submit_attempt(wav_bytes: bytes) -> dict:
    global attempt_num, current_level
    attempt_num += 1
    audio_b64 = base64.b64encode(wav_bytes).decode()
    r = requests.post(f"{SERVER}/attempt", data={
        "session_id":     session_id,
        "child_id":       CHILD_ID,
        "attempt_number": attempt_num,
        "current_level":  current_level,
        "target_phoneme": "s",
        "audio_b64":      audio_b64,
    }, timeout=10)
    r.raise_for_status()
    result = r.json()
    current_level = result["new_level"]
    history.append(result)
    return result


def get_session_summary() -> dict:
    r = requests.get(f"{SERVER}/session/{session_id}", timeout=5)
    r.raise_for_status()
    return r.json()


# ── Rendering ──────────────────────────────────────────────────────────────────

def render_result(result: dict):
    score    = result["score"]
    led      = result["led_state"]
    face     = result["face_state"]
    tts      = result["tts_text"]
    ftype    = result["feedback_type"]
    advance  = result["advance"]
    drop     = result["drop_back"]
    level    = result["new_level"]
    subs     = result.get("sub_scores", {})
    diag     = result.get("diagnostic", {})

    console.print()

    # LED simulation
    led_sym, led_col, led_label = LED_FRAMES.get(led, ("?", "white", led))
    ring = " ".join([led_sym] * 12)
    console.print(Panel(
        f"[bold {led_col}]{ring}[/]\n[{led_col}]{led_label}[/]",
        title="[bold]LED ring[/]",
        border_style=led_col,
        width=60,
    ))

    # OLED face
    face_str = FACE_FRAMES.get(face, "(•_•)")
    console.print(Panel(
        Align(f"[bold cyan]{face_str}[/]", align="center"),
        title="[bold]OLED face[/]",
        border_style="cyan",
        width=30,
    ))

    # TTS
    console.print(f'\n  [bold]Device says:[/] [italic cyan]"{tts}"[/]\n')

    # Score bar
    filled  = int(score * 20)
    colour  = "green" if score >= 0.70 else "yellow" if score >= 0.45 else "red"
    bar     = "█" * filled + "░" * (20 - filled)
    console.print(f"  Score  [{colour}][{bar}] {score:.2f}[/]  ({ftype})")

    # Sub-scores
    console.print(render_sub_scores(subs))

    # Diagnostic
    console.print(f"\n  [grey50]Centroid: {diag.get('centroid_hz',0):.0f}Hz — {diag.get('centroid_status','')}[/]")
    console.print(f"  [grey50]Duration: {diag.get('duration_ms',0):.0f}ms — {diag.get('duration_status','')}[/]")

    # Adaptive flags
    if advance:
        console.print(f"\n  [bold magenta]★ LEVEL UP → {level.upper()} ★[/]")
    elif drop:
        console.print(f"\n  [bold red]↓ Dropping to {level.upper()}[/]")
    else:
        console.print(f"\n  [grey50]Level: {level}  |  Attempt #{attempt_num}[/]")


def render_summary():
    try:
        s = get_session_summary()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            console.print("[yellow]No attempts yet in this session.[/]")
            return
        console.print(f"[red]Could not fetch summary: {e}[/]")
        return
    except Exception as e:
        console.print(f"[red]Could not fetch summary: {e}[/]")
        return

    table = Table(title="Session Summary", box=box.ROUNDED, border_style="cyan")
    table.add_column("Metric",    style="bold")
    table.add_column("Value",     style="cyan")

    table.add_row("Total attempts",    str(s["total_attempts"]))
    table.add_row("Average score",     str(s["average_score"]))
    table.add_row("Score trend",       s["score_trend"])
    table.add_row("Level reached",     s["level_reached"])
    table.add_row("Pitch correct",     f"{s['pitch_correct_pct']}%")
    table.add_row("Duration correct",  f"{s['duration_correct_pct']}%")
    table.add_row("Main challenge",    s["main_challenge"])

    console.print(table)

    # Score sparkline
    scores = [a["score"] for a in s.get("attempts", [])]
    if scores:
        spark = ""
        for sc in scores:
            if sc >= 0.70:   spark += "[green]▇[/]"
            elif sc >= 0.45: spark += "[yellow]▄[/]"
            else:            spark += "[red]▁[/]"
        console.print(f"\n  Scores: {spark}")


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    global session_id

    parser = argparse.ArgumentParser()
    parser.add_argument("--selfhost", action="store_true",
                        help="Start stage4_server automatically")
    parser.add_argument("--synthetic", action="store_true",
                        help="Skip mic, always use synthetic audio")
    args = parser.parse_args()

    # optionally start server in background
    server_proc = None
    if args.selfhost:
        console.print("[yellow]Starting ML server...[/]")
        server_proc = subprocess.Popen(
            [sys.executable, "stage4_server.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)
        console.print("[green]Server started on :8000[/]")

    if args.synthetic:
        global MIC_AVAILABLE
        MIC_AVAILABLE = False

    # check server
    try:
        requests.get(f"{SERVER}/health", timeout=3)
    except Exception:
        console.print(f"[red]Cannot reach server at {SERVER}[/]")
        console.print("[yellow]Run: python3 stage4_server.py  (or use --selfhost)[/]")
        sys.exit(1)

    # start session
    session_id = start_session()

    console.print(Panel(
        "[bold cyan]Speech Therapy Device — Laptop Demo[/]\n\n"
        "Target phoneme: [bold]/s/[/]\n"
        "Facilitative play: [italic]help the toy learn to speak![/]\n\n"
        "[grey50]SPACE/Enter = record  |  s = stats  |  q = quit[/]",
        border_style="cyan",
    ))
    console.print(f"[grey50]Session: {session_id[:8]}...  Level: {current_level}[/]\n")

    # main loop
    try:
        while True:
            cmd = console.input("[bold]  Press Enter to attempt, s=stats, q=quit:[/] ").strip().lower()

            if cmd == "q":
                break
            elif cmd == "s":
                render_summary()
                continue

            # record + submit
            wav = record_attempt()
            console.print("[grey50]  Analysing...[/]")

            try:
                result = submit_attempt(wav)
                render_result(result)
            except requests.RequestException as e:
                console.print(f"[red]  API error: {e}[/]")

    except KeyboardInterrupt:
        pass

    # end session
    console.print("\n[bold]Session complete.[/]")
    render_summary()

    if server_proc:
        server_proc.terminate()


if __name__ == "__main__":
    main()
