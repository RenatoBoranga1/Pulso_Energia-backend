# AGENTS.md

## Objective
Build a production-grade Python backend for intelligent energy bill ingestion, extraction, analytics, and forecasting.

## Technical stack
- Python 3.11+
- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- Pydantic
- Pandas
- Numpy
- pdfplumber
- Pillow
- pytesseract
- Docker

## Engineering rules
- Keep routes thin
- Put business logic in services
- Keep DB logic in repositories
- Use typed schemas for all API I/O
- Validate all extracted fields
- Never silently accept low-confidence extraction
- Mark low-confidence fields for manual review

## Forecasting
- Prefer Prophet or NeuralProphet when enough data exists
- Use deterministic fallback when data is insufficient
- Never fake confidence intervals
- Always expose which forecasting method was used

## Extraction
- Support PDF and images
- Extract raw text first
- Normalize before semantic parsing
- Return structured JSON with confidence per field
- Preserve original uploaded document metadata

## Done means
- Project runs locally
- Main API endpoints exist
- Upload + extraction flow works
- Forecast endpoint works
- Tests exist for main flows
- README explains setup and usage

