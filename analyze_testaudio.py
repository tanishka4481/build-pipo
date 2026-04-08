import argparse
from pathlib import Path

from stage1_preprocess import preprocess
from stage2_features import extract
from stage3_feedback import decide, SessionState


def classify(score: float, quality_ok: bool, hint: str) -> str:
    if not quality_ok and score == 0.0:
        return "no_attempt_or_silence"
    if not quality_ok and score > 0.0:
        return "wrong_or_unclear_phoneme"
    if score >= 0.7:
        return "strong_s"
    if score >= 0.45:
        return "developing_s"
    if hint in {"spectral_centroid", "wrong_phoneme"}:
        return "likely_substitution"
    if hint == "fricative_duration":
        return "timing_issue"
    return "weak_attempt"


def analyze_folder(folder: Path):
    files = sorted(
        [p for p in folder.iterdir() if p.suffix.lower() in {".wav", ".flac", ".ogg", ".mp3", ".m4a"}]
    )
    if not files:
        print(f"No audio files found in: {folder}")
        return 1

    state = SessionState(current_level="isolation")

    print("=" * 140)
    print("Methodology: each file is scored by the real pipeline (preprocess -> features -> feedback) and labeled from signals, not filename")
    print("=" * 140)
    print(
        f"{'file':28} {'quality':8} {'score':6} {'centroid_hz':11} {'flatness':8} {'zcr':6} {'dur_ms':7} {'feedback':11} {'hint':18} {'class'}"
    )
    print("-" * 140)

    for p in files:
        p1 = preprocess(str(p))
        fv = extract(p1)
        d = decide(fv, state)
        label = classify(fv.phoneme_score, fv.quality_ok, d.hint)

        print(
            f"{p.name[:28]:28} "
            f"{str(fv.quality_ok):8} "
            f"{fv.phoneme_score:6.2f} "
            f"{fv.spectral_centroid:11.0f} "
            f"{fv.spectral_flatness:8.3f} "
            f"{fv.zero_crossing_rate:6.3f} "
            f"{fv.fricative_duration * 1000:7.0f} "
            f"{d.feedback_type[:11]:11} "
            f"{d.hint[:18]:18} "
            f"{label}"
        )

    print("-" * 140)
    print(f"Final adaptive level after sequence: {state.current_level}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder",
        default=r"C:\Users\HP\Desktop\test_audio",
        help="Folder containing test audio clips",
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"Folder does not exist: {folder}")
        raise SystemExit(1)

    raise SystemExit(analyze_folder(folder))


if __name__ == "__main__":
    main()
