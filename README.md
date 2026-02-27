# Voice Support Engine

A FastAPI-based voice assistant backend (with a Streamlit demo UI) for handling support-style queries about test automation runs.

## Features

- Deterministic intent classification with confidence scoring.
- LLM fallback classification + slot extraction (Gemini) when deterministic confidence is low.
- Structured voice turn responses:
  - `intent`
  - `reply_text`
  - `suggested_actions`
  - `context_used`
  - `confidence`
  - `escalate`
- Action execution endpoint for supported operations (e.g., rerun test, get run status).
- Streamlit demo with:
  - Chat-style interface
  - Microphone input (via `SpeechRecognition`)
  - Manual text input fallback
  - Browser text-to-speech playback

## Project Structure

- `app/main.py` - FastAPI app and API routes.
- `app/services/` - Core logic (intent engine, response builder, action engine, fallback LLM, etc.).
- `app/schemas/` - Pydantic request/response models.
- `app/data/` - Mock data used by services.
- `demo_app.py` - Streamlit front-end demo.

## Requirements

- Python 3.10+
- Pip
- (Optional, for LLM fallback) Google Gemini API key

> Note: LLM fallback reads `GOOGLE_API_KEY` from environment variables.

## Setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. (Optional) Configure Gemini key for LLM fallback:

```bash
export GOOGLE_API_KEY="your_api_key_here"
```

## Run the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health check: `GET http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`

## Run the Demo UI

In a separate terminal (with API running):

```bash
streamlit run demo_app.py
```

Then open the local Streamlit URL shown in the terminal (usually `http://localhost:8501`).

## API Endpoints

### `POST /voice/turn`
Classifies user transcript, optionally falls back to LLM, and returns a support response.

Example request:

```json
{
  "transcript": "How did my last run go?",
  "user_id": 1,
  "project_id": 0,
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "context_summary": {}
}
```

### `POST /voice/action`
Executes an allowed action.

Example request:

```json
{
  "action_type": "get_run_status",
  "params": {}
}
```

## Notes

- This project currently uses mocked product API/context data for core flows.
- Some dependencies in `requirements.txt` are broad because they support both backend and demo experiments.
