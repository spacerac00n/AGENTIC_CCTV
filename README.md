# Surveillance 17

An AI-powered security co-pilot for campus CCTV that **detects threats**, **scores risk**, and **coordinates cross-camera tracking** in near real time—so incidents can be caught early and escalated with clear operator context.

## Why this matters
Many communities face delayed incident reporting and fragmented monitoring. Surveillance-17 turns basic CCTV feeds into a single operator workflow: **detect → explain → confirm → dispatch → track**.

## Key features
- **VLM-driven detection with reasoning**: outputs structured results plus a human-readable “Report Card”.
- **Risk scoring + color bands**: normal / monitor / alert / critical mapped from a 0–10 risk score.
- **Human-in-the-loop dispatch**: “Confirm dispatch” gates high-severity escalation.
- **Cross-camera tracking (demo)**: create a Track Card and search on another camera; reacquisition triggers “Target spotted” + map glow.
- **Resilient runtime**: uses **GPT-4o when available** with **Ollama fallback** for degraded connectivity / offline operation.
- **Privacy-forward**: no face recognition; supports local processing modes.

## Requirements
- Python 3.11+ (3.12 recommended)
- OpenAI API keys for best results (optional if you want to run Ollama-only)
- (Optional) Ollama running locally for fallback/offline inference

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration (environment variables)
Copy the example file and fill in values:
```bash
cp .env.example .env
```

Environment variables (see `.env.example`):
- `OPENAI_API_KEY` — primary vision/risk models
- `OPENAI_API_KEY_2` — (optional) tracking/BOLO flows
- `OLLAMA_HOST` — Ollama server URL (default: `http://localhost:11434`)
- `OLLAMA_VISION_MODEL` — vision-capable Ollama model name

## Running the app
1. Start Streamlit: Please wait awhile for the demo live feed to load (demo1.mov)
```bash
streamlit run main.py
```

## Testbench (for judges)
Include a `testbench/` folder in the repo with:
- A small sample video 
- A step-by-step `SETUP_AND_RUN.md` that mirrors the exact commands above
- Any assets needed for the map / demo flow

## Privacy & responsible use
- Surveillance 17 is a **decision-support** tool for authorized operators.
- No face recognition is required for the demo flow.
- If you run Ollama locally, frames can be processed without sending images to the cloud.


