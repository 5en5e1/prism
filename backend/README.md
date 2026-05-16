# Backend API

AI-powered HTML manipulation backend using FastAPI and OpenAI.

## Architecture

This backend implements a Strategy + Registry pattern where each use case (DOM manipulation, QA, redesign) is a self-contained handler. See [ARCHITECTURE.md](../ARCHITECTURE.md) for detailed design decisions.

## Setup

1. Install dependencies:
```bash
poetry install
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Add your OpenAI API key to `.env`

4. Run the server:
```bash
poetry run uvicorn app.main:app --reload
```

## API Endpoints

- `POST /api/v1/process` - Main processing endpoint
- `GET /health` - Health check

## Development

Run tests:
```bash
poetry run pytest
```

Format code:
```bash
poetry run black .
poetry run ruff check --fix .
```

Type checking:
```bash
poetry run mypy app
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── api/v1/              # API routes
│   ├── core/                # Core pipeline logic
│   ├── handlers/            # Use case handlers
│   ├── ai/                  # OpenAI client
│   ├── preprocessing/       # HTML processing
│   ├── prompts/             # Prompt templates
│   ├── schemas/             # Pydantic models
│   └── utils/               # Utilities
└── tests/                   # Test suite