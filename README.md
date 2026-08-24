# Merchant-as-a-Tool Agent Gateway

## Project Purpose
Merchant-as-a-Tool Agent Gateway turns any merchant's product catalog into safe, tool-callable APIs so external AI buyer agents can discover products, create carts, and complete payments with strict guardrails and auditability.

## Current Scope (Part 1 — Project Foundation)
This repository is currently at **Part 1: Project Foundation**.
- FastAPI application setup with configuration loading (`python-dotenv`).
- Baseline SQLite database connection handling (no business tables yet).
- Health check endpoint (`GET /health`).
- Minimal test suite with `pytest`.
- Prepared configuration for local LLM inference with Ollama & Qwen.

## Setup Instructions

### 1. Prerequisites
- Python 3.11+
- Git
- (Optional for later parts) [Ollama](https://ollama.com/) for local LLM inference

### 2. Environment Setup
Create and activate a virtual environment:

```bash
python -m venv .venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Initialize environment configuration:
```bash
copy .env.example .env
```

### 3. Ollama & Qwen Setup (Local LLM)
1. Install and start Ollama on your machine.
2. Pull the Qwen model:
```bash
ollama pull qwen2.5:7b
```
3. Ensure Ollama is running at `http://localhost:11434` (configured in `.env`).

## Running the Application

Start the FastAPI application using the runner script:
```bash
python run.py
```
Or directly with Uvicorn:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Access the interactive API docs at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

## Running Tests

Run the test suite using pytest:
```bash
pytest
```
