# Protein AI Platform

AI-powered protein research agent platform with MCP tool integration.

## Quick Start

```bash
# Start all services
cd docker
docker compose up -d

# Or run individually:
# Frontend
cd frontend && npm install && npm run dev

# Backend
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
```

## Architecture

```
Browser → Nginx → React SPA (port 3000)
              → FastAPI (port 8000)
                   ├── Agent Orchestrator
                   ├── MCP Server (tool registry)
                   ├── PostgreSQL (data)
                   ├── Redis (cache/queue)
                   ├── MinIO (file storage)
                   └── Celery Workers (GPU tasks)
```

## API

See http://localhost:8000/docs for interactive API documentation.

## Environment

Copy `backend/.env.example` to `backend/.env` and configure your LLM API keys.
