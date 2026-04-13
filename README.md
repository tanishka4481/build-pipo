# POPI

POPI is a passive companion toy for children aged 3-5 with /s/ sound substitution, designed to make practice feel like play. It runs 90-second micro-sessions where the child "teaches" the toy, while the backend scores acoustic quality and logs progress for weekly SLP review.

## What Is In This Repo

- FastAPI backend in `stage4_server.py`
- Acoustic scoring pipeline in `stage1_preprocess.py`, `stage2_features.py`, `stage3_feedback.py`
- Laptop demo client in `laptop_demo.py`
- Test harness in `stage5_tests.py`
- Demo data seeder in `seed_demo_data.py`

## Install

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

## Run Locally

Start the API server:

```powershell
python stage4_server.py
```

In a second terminal, run the laptop demo:

```powershell
python laptop_demo.py
```

One-shot mode (starts server automatically):

```powershell
python laptop_demo.py --selfhost
```

No-mic mode:

```powershell
python laptop_demo.py --synthetic --selfhost
```

## Run Tests

Quick regression pass:

```powershell
python stage5_tests.py --quick
```

## Seed Demo Data

Local server:

```powershell
python seed_demo_data.py
```

Remote Render server:

```powershell
python seed_demo_data.py --server https://popi-api.onrender.com
```

## Deploy To Render

This repo includes `render.yaml` for Blueprint deploy.

1. Push this repository to GitHub.
2. In Render, create a new Blueprint and select the repo.
3. Use a free external Postgres database provider such as Supabase or Neon.
4. Copy the Postgres connection string into `DATABASE_URL` in Render.
5. Deploy and verify:

```text
GET /healthz
GET /ping
```

Optional keep-warm on free tier: ping `/ping` every 10 minutes from cron-job.org.

### Free Tier Database Plan

Render Free does not support persistent disks, so the API now uses an external Postgres database.

Recommended setup:

1. Create a free Supabase project.
2. Copy the PostgreSQL connection string from Supabase.
3. Set `DATABASE_URL` in Render to that string.
4. Keep `VITE_API_BASE_URL` pointed at the Render service in the frontend when deployed.

## Demo Day Run Order

```powershell
# 1. Start server
python stage4_server.py

# 2. Seed demo data (run once)
python seed_demo_data.py

# 3. Run live demo
python laptop_demo.py --selfhost

# 4. If no mic available
python laptop_demo.py --synthetic --selfhost

# 5. Quick regression check before demo
python stage5_tests.py --quick

# 6. Test on real audio files
python analyze_testaudio.py --folder "C:\Users\HP\Desktop\test_audio"
```
