# POPI System

POPI is an ambient companion toy designed to bridge the gap between weekly speech therapy sessions. Disguised as a cute desk pet, it leverages a 90-second micro-moment interaction to help children practice articulation and build motor memory. 

The child teaches the “toy,” promoting speech via Facilitative Play. This repo contains the offline acoustic scoring models, system algorithms, therapy workflows, database implementation, APIs, and the clinical dashboard.

## Installation 

1. Install Python 3.10+
2. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

## Demo Execution Instructions

The complete user pipeline for demoing POPI is as follows:

1. **Start server**
   ```bash
   python stage4_server.py
   ```

2. **Seed demo data (run once to pre-populate DB for Arjun's profile)**
   ```bash
   python seed_demo_data.py
   ```

3. **Run live demo (use terminal 2)**
   ```bash
   # Option A: Uses physical mic
   python laptop_demo.py --selfhost

   # Option B: No mic available, uses synthetic speech files
   python laptop_demo.py --synthetic --selfhost
   ```

4. **Regression Check (ensure models are accurate)**
   ```bash
   python stage5_tests.py --quick
   ```

## React Dashboard

The clinical dashboard is built with React and Vite. It serves as the frontend for the SLP.
`cd dashboard` and `npm install` followed by `npm run dev` running locally at standard Vite port.

## Deployment

The backend server is meant to be hosted via [Render](https://render.com/). There is an included `render.yaml` file configuring the web service to automatically deploy the `stage4_server` with FastAPI when pushing to the GitHub repository. It mounts the persistence disk `/data` to persist our SQLite `popi.db` database.
