"""
Stage 4 — FastAPI Server
==========================
Wraps Stages 1–3 into a single HTTP endpoint.
Writes diagnostic data to SQLite (swap to Postgres in prod).

Endpoints:
    POST /attempt          — main loop (audio in → decision out + DB write)
    POST /session/start    — create a new session, returns session_id
    GET  /session/{id}     — fetch session summary (diagnostic framing for parents)
    GET  /health           — liveness check

Request  (multipart/form-data OR JSON with base64):
    session_id      str
    child_id        str
    attempt_number  int
    current_level   str
    target_phoneme  str   (only "s" supported in MVP)
    audio           file  (WAV) OR audio_b64 str (base64 WAV)

Response (JSON):
    score           float
    feedback_type   str
    led_state       str
    face_state      str
    servo_action    str
    tts_text        str
    advance         bool
    drop_back       bool
    new_level       str
    db_written      bool
    hint            str
    sub_scores      dict
    diagnostic      dict   — human-readable breakdown for logging
"""

import os
import uuid
import base64
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta, date
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import soundfile as sf
import io

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    Boolean, DateTime, Text, ForeignKey, JSON, func, text
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from stage1_preprocess import preprocess
from stage2_features    import extract, FeatureVector
from stage3_feedback    import decide, SessionState, FeedbackDecision

try:
    from config import WORD_BANK as CONFIG_WORD_BANK  # type: ignore
except Exception:
    CONFIG_WORD_BANK = {
        "phoneme": [{"word": "sss", "prompt": "Can you help me make the wind sound?"}],
        "syllable": [{"word": "see", "prompt": "Can you help me say see?"}],
        "word_init": [{"word": "sun", "prompt": "Can you help me say sun?"}],
        "word_final": [{"word": "bus", "prompt": "Can you help me say bus?"}],
        "word_med": [{"word": "outside", "prompt": "Can you help me say outside?"}],
        "phrase": [{"word": "the sun is hot", "prompt": "Can you help me say the sun is hot?"}],
    }

try:
    from noise_reduction import denoise  # type: ignore
except Exception:
    def denoise(raw_bytes: bytes) -> bytes:
        return raw_bytes

# ── DB setup ───────────────────────────────────────────────────────────────────
DEFAULT_SQLITE_PATH = Path(__file__).with_name("speech_therapy.db")
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}")


def _build_engine(database_url: str):
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True)


engine  = _build_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base    = declarative_base()


class DBSession(Base):
    """One micro-session (up to ~90 seconds of interactions)."""
    __tablename__ = "sessions"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    child_id        = Column(String, nullable=False, index=True)
    started_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at        = Column(DateTime, nullable=True)
    level           = Column(String, default="isolation")
    target_phoneme  = Column(String, default="s")
    total_attempts  = Column(Integer, default=0)
    final_score_avg = Column(Float,   nullable=True)


class DBChild(Base):
    __tablename__ = "children"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name            = Column(String, nullable=False)
    age             = Column(Integer, nullable=False)
    disorder_type   = Column(String, default="articulation")
    target_phoneme  = Column(String, default="s")
    slp_id          = Column(String, nullable=True)
    notes           = Column(Text, nullable=True)


class DBWordPlan(Base):
    __tablename__ = "word_plans"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    child_id        = Column(String, ForeignKey("children.id"), nullable=False, index=True)
    week_start      = Column(String, nullable=False)
    word_list       = Column(JSON, nullable=False)
    start_level     = Column(String, default="phoneme")
    pass_threshold  = Column(Float, default=0.70)
    max_attempts    = Column(Integer, default=5)
    pushed_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    synced_at       = Column(DateTime, nullable=True)


class DBAttempt(Base):
    """One child attempt — single phoneme production."""
    __tablename__ = "attempts"

    id                  = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id          = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    child_id            = Column(String, nullable=False)
    timestamp           = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    attempt_number      = Column(Integer)
    level               = Column(String)
    target_phoneme      = Column(String)
    target_word         = Column(String, nullable=True)

    # scores
    phoneme_score       = Column(Float)
    feedback_type       = Column(String)   # praise | corrective | model | no_attempt
    hint                = Column(String)   # which feature was weak

    # sub-scores (diagnostic — what parents/SLP can read)
    sub_centroid        = Column(Float)    # spectral centroid score 0-1
    sub_flatness        = Column(Float)    # spectral flatness score 0-1
    sub_zcr             = Column(Float)    # zero crossing rate score 0-1
    sub_duration        = Column(Float)    # duration score 0-1

    # raw feature values
    raw_centroid_hz     = Column(Float)
    raw_duration_ms     = Column(Float)

    # diagnostic booleans
    pitch_correct       = Column(Boolean)
    duration_correct    = Column(Boolean)

    # what the device did
    led_state           = Column(String)
    face_state          = Column(String)
    advance_triggered   = Column(Boolean, default=False)
    drop_triggered      = Column(Boolean, default=False)


class DBAlert(Base):
    __tablename__ = "alerts"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    child_id        = Column(String, ForeignKey("children.id"), nullable=False, index=True)
    alert_type      = Column(String, nullable=False)  # parent | slp
    category        = Column(String, nullable=False)
    message         = Column(Text, nullable=False)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    dismissed_at    = Column(DateTime, nullable=True)
    dismissed_by    = Column(String, nullable=True)


Base.metadata.create_all(bind=engine)


def _ensure_sqlite_columns() -> None:
    if make_url(DB_URL).get_backend_name() != "sqlite":
        return
    db = SessionLocal()
    try:
        # Backward-compatible add for older attempts table.
        pragma = db.execute(text("PRAGMA table_info(attempts)")).fetchall()
        cols = {row[1] for row in pragma}
        if "target_word" not in cols:
            db.execute(text("ALTER TABLE attempts ADD COLUMN target_word VARCHAR"))
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


_ensure_sqlite_columns()

# ── In-memory session state store ─────────────────────────────────────────────
# In prod: move to Redis. For hackathon: dict keyed by session_id.
_session_states: dict[str, SessionState] = {}

def get_or_create_state(session_id: str, level: str = "isolation") -> SessionState:
    if session_id not in _session_states:
        _session_states[session_id] = SessionState(current_level=level)
    return _session_states[session_id]


# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Speech therapy ML server starting...")
    yield
    print("Shutting down.")

app = FastAPI(title="Speech Therapy ML API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    child_id:       str
    level:          str = "isolation"
    target_phoneme: str = "s"

class SessionStartResponse(BaseModel):
    session_id: str
    level:      str
    message:    str

class AttemptResponse(BaseModel):
    score:          float
    feedback_type:  str
    led_state:      str
    face_state:     str
    servo_action:   str
    tts_text:       str
    advance:        bool
    drop_back:      bool
    new_level:      str
    db_written:     bool
    hint:           str
    sub_scores:     dict
    diagnostic:     dict


class SessionEndRequest(BaseModel):
    session_id: str
    total_attempts: Optional[int] = None
    avg_score: Optional[float] = None


class ChildCreateRequest(BaseModel):
    name: str
    age: int
    disorder_type: str = "articulation"
    target_phoneme: str = "s"
    slp_id: Optional[str] = None
    notes: Optional[str] = None


class PlanPushRequest(BaseModel):
    child_id: str
    week_start: str
    word_list: list
    start_level: str = "phoneme"
    pass_threshold: float = 0.70
    max_attempts: int = 5


class AlertDismissRequest(BaseModel):
    alert_id: str
    dismissed_by: str = "slp"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/healthz")
async def healthz():
    return await health()


@app.get("/ping")
async def ping():
    return {"status": "ok", "ping": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/child/create")
async def create_child(req: ChildCreateRequest, db: Session = Depends(get_db)):
    child = DBChild(
        name=req.name,
        age=req.age,
        disorder_type=req.disorder_type,
        target_phoneme=req.target_phoneme,
        slp_id=req.slp_id,
        notes=req.notes,
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return {"child_id": child.id, "name": child.name}


@app.get("/children")
async def get_children(db: Session = Depends(get_db)):
    rows = db.query(DBChild).order_by(DBChild.name.asc()).all()
    return {
        "children": [
            {
                "id": c.id,
                "name": c.name,
                "age": c.age,
                "target_phoneme": c.target_phoneme,
                "disorder_type": c.disorder_type,
            }
            for c in rows
        ]
    }


@app.get("/child/{child_id}")
async def get_child_profile(child_id: str, db: Session = Depends(get_db)):
    child = db.query(DBChild).filter(DBChild.id == child_id).first()
    if not child:
        raise HTTPException(404, "Child not found")

    sessions = (
        db.query(DBSession)
        .filter(DBSession.child_id == child_id)
        .order_by(DBSession.started_at.desc())
        .all()
    )
    alerts = (
        db.query(DBAlert)
        .filter(DBAlert.child_id == child_id, DBAlert.dismissed_at.is_(None))
        .order_by(DBAlert.created_at.desc())
        .all()
    )

    daily: dict[str, list[float]] = {}
    for s in sessions:
        if s.final_score_avg is None or s.started_at is None:
            continue
        day_key = s.started_at.date().isoformat()
        daily.setdefault(day_key, []).append(float(s.final_score_avg))

    daily_scores = [
        {
            "date": day,
            "avg_score": round(sum(vals) / len(vals), 3),
            "n_sessions": len(vals),
        }
        for day, vals in sorted(daily.items())
    ]

    return {
        "child": {
            "id": child.id,
            "name": child.name,
            "age": child.age,
            "disorder_type": child.disorder_type,
            "target_phoneme": child.target_phoneme,
            "slp_id": child.slp_id,
            "notes": child.notes,
        },
        "session_history": [
            {
                "session_id": s.id,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "level": s.level,
                "target_phoneme": s.target_phoneme,
                "total_attempts": s.total_attempts,
                "final_score_avg": s.final_score_avg,
            }
            for s in sessions
        ],
        "daily_scores": daily_scores,
        "alerts": [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "category": a.category,
                "message": a.message,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ],
    }


@app.post("/plan/push")
async def push_plan(req: PlanPushRequest, db: Session = Depends(get_db)):
    child = db.query(DBChild).filter(DBChild.id == req.child_id).first()
    if not child:
        raise HTTPException(404, "Child not found")

    plan = DBWordPlan(
        child_id=req.child_id,
        week_start=req.week_start,
        word_list=req.word_list,
        start_level=req.start_level,
        pass_threshold=req.pass_threshold,
        max_attempts=req.max_attempts,
        pushed_at=datetime.now(timezone.utc),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {"plan_id": plan.id, "child_id": plan.child_id, "week_start": plan.week_start}


@app.get("/plan/sync")
async def sync_plan(child_id: str, db: Session = Depends(get_db)):
    plan = (
        db.query(DBWordPlan)
        .filter(DBWordPlan.child_id == child_id)
        .order_by(DBWordPlan.pushed_at.desc())
        .first()
    )
    if not plan:
        return {"child_id": child_id, "has_plan": False, "word_list": []}

    plan.synced_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "child_id": child_id,
        "has_plan": True,
        "plan": {
            "plan_id": plan.id,
            "week_start": plan.week_start,
            "word_list": plan.word_list,
            "start_level": plan.start_level,
            "pass_threshold": plan.pass_threshold,
            "max_attempts": plan.max_attempts,
            "pushed_at": plan.pushed_at.isoformat() if plan.pushed_at else None,
            "synced_at": plan.synced_at.isoformat() if plan.synced_at else None,
        },
    }


@app.get("/alerts/{child_id}")
async def get_alerts(child_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(DBAlert)
        .filter(DBAlert.child_id == child_id, DBAlert.dismissed_at.is_(None))
        .order_by(DBAlert.created_at.desc())
        .all()
    )
    return {
        "alerts": [
            {
                "id": a.id,
                "child_id": a.child_id,
                "alert_type": a.alert_type,
                "category": a.category,
                "message": a.message,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ]
    }


@app.post("/alert/dismiss")
async def dismiss_alert(req: AlertDismissRequest, db: Session = Depends(get_db)):
    alert = db.query(DBAlert).filter(DBAlert.id == req.alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.dismissed_at = datetime.now(timezone.utc)
    alert.dismissed_by = req.dismissed_by
    db.commit()
    return {"ok": True, "alert_id": alert.id}


@app.get("/word-bank")
async def word_bank():
    return {"word_bank": CONFIG_WORD_BANK}


@app.post("/session/start", response_model=SessionStartResponse)
async def start_session(req: SessionStartRequest, db: Session = Depends(get_db)):
    """Create a new session. Call this when proximity sensor triggers."""
    sess_id = str(uuid.uuid4())

    db_sess = DBSession(
        id             = sess_id,
        child_id       = req.child_id,
        level          = req.level,
        target_phoneme = req.target_phoneme,
    )
    db.add(db_sess)
    db.commit()

    # init session state
    _session_states[sess_id] = SessionState(current_level=req.level)

    return SessionStartResponse(
        session_id = sess_id,
        level      = req.level,
        message    = "session started",
    )


@app.post("/session/end")
async def end_session(req: SessionEndRequest, db: Session = Depends(get_db)):
    db_sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
    if not db_sess:
        raise HTTPException(404, "Session not found")

    attempts = db.query(DBAttempt).filter(DBAttempt.session_id == req.session_id).all()
    scores = [a.phoneme_score for a in attempts if a.phoneme_score is not None]

    db_sess.ended_at = datetime.now(timezone.utc)
    db_sess.total_attempts = req.total_attempts if req.total_attempts is not None else len(attempts)
    db_sess.final_score_avg = (
        req.avg_score
        if req.avg_score is not None
        else (round(sum(scores) / len(scores), 3) if scores else 0.0)
    )
    db.commit()

    _session_states.pop(req.session_id, None)
    _evaluate_alerts(db_sess.child_id, db)

    return {
        "session_id": req.session_id,
        "closed": True,
        "total_attempts": db_sess.total_attempts,
        "final_score_avg": db_sess.final_score_avg,
    }


@app.post("/attempt", response_model=AttemptResponse)
async def submit_attempt(
    session_id:     str        = Form(...),
    child_id:       str        = Form(...),
    attempt_number: int        = Form(...),
    current_level:  str        = Form("isolation"),
    target_phoneme: str        = Form("s"),
    target_word:    str        = Form(""),
    audio:          UploadFile = File(None),
    audio_b64:      str        = Form(None),
    db: Session = Depends(get_db),
):
    """
    Main endpoint. Accepts a WAV file OR base64-encoded WAV string.
    Runs the full pipeline: preprocess → extract → decide → write DB → return JSON.
    """
    # ── 1. Load audio ──────────────────────────────────────────────────────────
    if audio is not None:
        raw_bytes = await audio.read()
    elif audio_b64:
        try:
            raw_bytes = base64.b64decode(audio_b64)
        except Exception:
            raise HTTPException(400, "Invalid base64 audio data")
    else:
        raise HTTPException(400, "Provide either audio file or audio_b64")

    # ── 2. Pipeline ───────────────────────────────────────────────────────────
    try:
        clean_bytes = await asyncio.get_event_loop().run_in_executor(
            None, denoise, raw_bytes
        )
        preprocess_result = await asyncio.get_event_loop().run_in_executor(
            None, preprocess, clean_bytes
        )
        feature_vector = await asyncio.get_event_loop().run_in_executor(
            None, extract, preprocess_result
        )
    except Exception as e:
        raise HTTPException(500, f"Pipeline error: {str(e)}")

    state    = get_or_create_state(session_id, current_level)
    decision = decide(feature_vector, state)

    # ── 3. Write to DB ────────────────────────────────────────────────────────
    db_written = False
    try:
        attempt = DBAttempt(
            session_id      = session_id,
            child_id        = child_id,
            attempt_number  = attempt_number,
            level           = current_level,
            target_phoneme  = target_phoneme,
            target_word     = target_word or None,
            phoneme_score   = feature_vector.phoneme_score,
            feedback_type   = decision.feedback_type,
            hint            = decision.hint,
            sub_centroid    = feature_vector.sub_scores.get("spectral_centroid", 0),
            sub_flatness    = feature_vector.sub_scores.get("spectral_flatness", 0),
            sub_zcr         = feature_vector.sub_scores.get("zero_crossing_rate", 0),
            sub_duration    = feature_vector.sub_scores.get("fricative_duration", 0),
            raw_centroid_hz = feature_vector.spectral_centroid,
            raw_duration_ms = feature_vector.fricative_duration * 1000,
            pitch_correct   = feature_vector.pitch_correct,
            duration_correct= feature_vector.duration_correct,
            led_state       = decision.led_state,
            face_state      = decision.face_state,
            advance_triggered = decision.advance,
            drop_triggered    = decision.drop_back,
        )
        db.add(attempt)

        # update session total
        db_sess = db.query(DBSession).filter(DBSession.id == session_id).first()
        if db_sess:
            db_sess.total_attempts += 1
            db_sess.level           = state.current_level

        db.commit()
        db_written = True
    except Exception as e:
        print(f"[DB ERROR] {e}")

    # ── 4. Build diagnostic dict (SLP-readable, not pass/fail) ────────────────
    diagnostic = _build_diagnostic(feature_vector, decision)

    return AttemptResponse(
        score         = feature_vector.phoneme_score,
        feedback_type = decision.feedback_type,
        led_state     = decision.led_state,
        face_state    = decision.face_state,
        servo_action  = decision.servo_action,
        tts_text      = decision.tts_text,
        advance       = decision.advance,
        drop_back     = decision.drop_back,
        new_level     = state.current_level,
        db_written    = db_written,
        hint          = decision.hint,
        sub_scores    = feature_vector.sub_scores,
        diagnostic    = diagnostic,
    )


@app.get("/session/{session_id}")
async def get_session(session_id: str, db: Session = Depends(get_db)):
    """
    Return a session summary with diagnostic framing.
    This is what a parent or SLP would read — not pass/fail, but feature breakdown.
    """
    attempts = (
        db.query(DBAttempt)
        .filter(DBAttempt.session_id == session_id)
        .order_by(DBAttempt.timestamp)
        .all()
    )
    if not attempts:
        raise HTTPException(404, "Session not found or no attempts yet")

    scores     = [a.phoneme_score for a in attempts if a.phoneme_score is not None]
    avg_score  = round(sum(scores) / len(scores), 3) if scores else 0.0

    # diagnostic language — what was the child's main challenge?
    hints      = [a.hint for a in attempts if a.hint and a.hint not in ("none", "no_audio")]
    main_hint  = max(set(hints), key=hints.count) if hints else "none"

    hint_descriptions = {
        "spectral_centroid":  "pitch placement — tongue position and airflow direction",
        "spectral_flatness":  "breath support — sustaining smooth airflow",
        "zero_crossing_rate": "fricative crispness — high-frequency noise quality",
        "fricative_duration": "duration control — holding the sound long enough",
        "wrong_phoneme":      "phoneme identification — producing /s/ vs similar sounds",
        "none":               "no consistent weakness — good overall production",
    }

    return {
        "session_id":      session_id,
        "total_attempts":  len(attempts),
        "average_score":   avg_score,
        "main_challenge":  hint_descriptions.get(main_hint, main_hint),
        "pitch_correct_pct":    _pct(attempts, "pitch_correct"),
        "duration_correct_pct": _pct(attempts, "duration_correct"),
        "level_reached":   attempts[-1].level if attempts else "isolation",
        "score_trend":     _trend(scores),
        "attempts":        [
            {
                "attempt_number": a.attempt_number,
                "score":          a.phoneme_score,
                "feedback_type":  a.feedback_type,
                "hint":           a.hint,
                "pitch_correct":  a.pitch_correct,
                "duration_correct": a.duration_correct,
            }
            for a in attempts
        ],
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _create_alert_if_missing(
    db: Session,
    child_id: str,
    alert_type: str,
    category: str,
    message: str,
) -> None:
    existing = (
        db.query(DBAlert)
        .filter(
            DBAlert.child_id == child_id,
            DBAlert.alert_type == alert_type,
            DBAlert.category == category,
            DBAlert.dismissed_at.is_(None),
        )
        .first()
    )
    if existing:
        return
    db.add(
        DBAlert(
            child_id=child_id,
            alert_type=alert_type,
            category=category,
            message=message,
        )
    )
    db.commit()


def _evaluate_alerts(child_id: str, db: Session) -> None:
    sessions = (
        db.query(DBSession)
        .filter(DBSession.child_id == child_id)
        .order_by(DBSession.started_at.desc())
        .all()
    )
    if not sessions:
        return

    latest_practice = sessions[0].started_at.date() if sessions[0].started_at else None
    if latest_practice is not None:
        gap_days = (datetime.now(timezone.utc).date() - latest_practice).days
        if gap_days >= 2:
            _create_alert_if_missing(
                db,
                child_id,
                "parent",
                "no_practice_2d",
                "No practice detected in the last 2 days.",
            )
        if gap_days >= 3:
            _create_alert_if_missing(
                db,
                child_id,
                "slp",
                "no_practice_3d",
                "No practice detected in the last 3 days.",
            )

    attempts = (
        db.query(DBAttempt)
        .filter(DBAttempt.child_id == child_id, DBAttempt.raw_centroid_hz.isnot(None))
        .order_by(DBAttempt.timestamp.desc())
        .all()
    )

    by_day: dict[str, list[float]] = {}
    for a in attempts:
        if a.timestamp is None or a.raw_centroid_hz is None:
            continue
        k = a.timestamp.date().isoformat()
        by_day.setdefault(k, []).append(float(a.raw_centroid_hz))

    recent_days = sorted(by_day.keys(), reverse=True)[:3]
    if len(recent_days) == 3:
        low_3d = all((sum(by_day[d]) / len(by_day[d])) < 4000.0 for d in recent_days)
        if low_3d:
            _create_alert_if_missing(
                db,
                child_id,
                "slp",
                "centroid_low_3d",
                "Centroid has remained low for 3 days. Placement may be regressing.",
            )

def _build_diagnostic(fv: FeatureVector, d: FeedbackDecision) -> dict:
    """Human-readable feature breakdown for logging / SLP export."""
    return {
        "centroid_hz":       round(fv.spectral_centroid, 1),
        "centroid_status":   "good" if fv.pitch_correct else "low — likely substitution or no airflow",
        "duration_ms":       round(fv.fricative_duration * 1000, 1),
        "duration_status":   "good" if fv.duration_correct else "too short — insufficient breath support",
        "flatness":          round(fv.spectral_flatness, 3),
        "flatness_status":   "good" if fv.spectral_match >= 0.5 else "low — tonal/voiced bleed",
        "overall_quality":   "quality attempt" if fv.quality_ok else "no clean fricative detected",
        "weakest_feature":   d.hint,
    }

def _pct(attempts, field: str) -> float:
    vals = [getattr(a, field) for a in attempts if getattr(a, field) is not None]
    return round(sum(vals) / len(vals) * 100, 1) if vals else 0.0

def _trend(scores: list) -> str:
    if len(scores) < 3:
        return "not enough data"
    recent = scores[-3:]
    if recent[-1] > recent[0] + 0.05:
        return "improving"
    if recent[-1] < recent[0] - 0.05:
        return "declining"
    return "stable"


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("stage4_server:app", host="0.0.0.0", port=8000, reload=True)
