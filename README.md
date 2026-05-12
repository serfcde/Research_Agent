# Research Agent - Production Agentic Research System

A production-level multi-agent research pipeline built with FastAPI, OpenAI, and Tavily API. Orchestrates specialized agents (Prompt Clarifier → Planner → Worker → Formatter) to automatically research topics and generate professional reports.

## Features

✨ **Multi-Agent Orchestration**
- Prompt Clarifier: Parse & structure user queries
- Planner: Decompose research into tasks
- Worker: Execute concurrent web searches
- Formatter: Generate professional reports

🚀 **Production-Ready Architecture**
- Async/concurrent task execution (5 parallel searches)
- Structured Pydantic validation
- Comprehensive error handling with retries
- Detailed logging & observability
- Fully containerized with Docker
- Unit & integration tests

📊 **Research Capabilities**
- Multi-topic research with comparative analysis
- Configurable research depth (quick/medium/deep)
- 5 concurrent web searches per topic
- LLM-powered summarization
- Citation tracking
- TXT file export

## ✅ Implementation Status

- ✅ Prompt Clarifier Agent - Complete
- ✅ Planner Agent - Complete
- ✅ Worker Agent - Complete
- ✅ Tools Integration (Web Search, File Writer) - Complete
- ✅ FastAPI Routes & Orchestration - Complete
- ✅ Comprehensive Unit & Integration Tests (25 tests passing)
- ✅ Docker Configuration - Complete
- ⏳ PostgreSQL Database Integration - Optional Enhancement

## Quick Start

### Prerequisites

- Python 3.14+ (tested with 3.14.3)
- OpenAI API key
- Tavily API key (or SerpAPI fallback)

### Setup

1. **Clone & Configure**
   ```bash
   git clone <repo>
   cd Research_Agent
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Create Virtual Environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Run Application**
   ```bash
   python -m uvicorn app.main:app --reload
   ```

   Access API at: `http://localhost:8000`
   - 📖 Interactive docs: http://localhost:8000/docs
   - 🔍 OpenAPI schema: http://localhost:8000/openapi.json

### Docker Setup

```bash
# Build image
docker build -f docker/Dockerfile -t research-agent .

# Run with environment
docker run -e OPENAI_API_KEY=sk-... -e TAVILY_API_KEY=... -p 8000:8000 research-agent

# Or use docker-compose
docker-compose -f docker/docker-compose.yml up
```

## API Endpoints

### 1. Enhance Prompt
```bash
POST /api/enhance-prompt
Content-Type: application/json

{
  "prompt": "Research quantum computing and edge AI"
}
```

**Response:**
```json
{
  "topics": ["Quantum Computing", "Edge AI"],
  "research_depth": "medium",
  "required_sections": ["Overview", "Applications", "Challenges", "Future Trends"],
  "compare_topics": true,
  "focus_areas": []
}
```

### 2. Plan Research
```bash
POST /api/plan-research
Content-Type: application/json

{
  "enhanced_prompt": {...}
}
```

**Response:**
```json
{
  "tasks": [
    {
      "task_id": 1,
      "topic": "Quantum Computing",
      "subtopic": "overview",
      "search_query": "quantum computing overview 2026",
      "description": "Get overview of quantum computing"
    },
    ...
  ]
}
```

### 3. Execute Research
```bash
POST /api/execute-research
Content-Type: application/json

{
  "tasks": [...]
}
```

**Response:**
```json
{
  "results": [
    {
      "task_id": 1,
      "topic": "Quantum Computing",
      "subtopic": "overview",
      "status": "completed",
      "findings": "...",
      "sources": [...],
      "execution_time_seconds": 5.2
    },
    ...
  ]
}
```

### 4. Format Report
```bash
POST /api/format-report
Content-Type: application/json

{
  "task_results": [...],
  "enhanced_prompt": {...}
}
```

**Response:**
```json
{
  "title": "Research Report: Quantum Computing and Edge AI",
  "topics": ["Quantum Computing", "Edge AI"],
  "introduction": "...",
  "sections": {...},
  "comparative_analysis": "...",
  "conclusion": "...",
  "citations": [...],
  "generated_at": "2026-05-11T12:00:00",
  "total_words": 3500
}
```

### 5. Full Pipeline (End-to-End)
```bash
POST /api/research
Content-Type: application/json

{
  "prompt": "Research AI in healthcare and blockchain in banking"
}
```

**Response:**
```json
{
  "report": {
    "title": "Research Report: AI in Healthcare, Blockchain in Banking",
    "topics": [...],
    ...
  },
  "file_path": "/research_outputs/research_ai_blockchain_20260511_120000.txt",
  "status": "completed",
  "total_execution_time_seconds": 125.4
}
```

## Project Structure

```
Research_Agent/
├── app/
│   ├── agents/
│   │   ├── prompt_enhancer.py      # Clarify user prompts
│   │   ├── planner.py              # Decompose into tasks
│   │   ├── worker.py               # Execute tasks concurrently
│   │   └── formatter.py            # Format reports
│   ├── tools/
│   │   ├── web_search.py           # Tavily + SerpAPI integration
│   │   └── file_writer.py          # TXT file export
│   ├── services/
│   │   ├── llm_service.py          # OpenAI wrapper
│   │   └── orchestration.py        # Main pipeline coordinator
│   ├── models/
│   │   └── schemas.py              # Pydantic validation models
│   ├── api/
│   │   └── routes.py               # FastAPI endpoints
│   ├── config/
│   │   └── settings.py             # Configuration management
│   ├── utils/
│   │   └── logger.py               # Structured logging
│   └── main.py                     # FastAPI app entry point
├── tests/
│   ├── test_agents.py
│   ├── test_integration.py
│   └── fixtures.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── research_outputs/               # Generated reports
├── logs/                           # Application logs
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```

## Configuration

### Environment Variables

```bash
# LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Web Search
TAVILY_API_KEY=...
SERPAPI_API_KEY=...              # Fallback

# Research
RESEARCH_OUTPUT_DIR=./research_outputs
TAVILY_MAX_CONCURRENT_SEARCHES=5
TAVILY_SEARCH_TIMEOUT_SECONDS=30

# Application
APP_DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
```

## Performance

Typical end-to-end performance for 2-topic research:
- **Prompt clarification**: ~2-3 seconds
- **Planning**: ~2-3 seconds
- **Task execution (6 tasks, concurrent)**: ~30-45 seconds
- **Formatting & file export**: ~5-10 seconds
- **Total**: ~40-60 seconds

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_agents.py -v

# Run with logging
pytest -v -s
```

## Logging

Logs are written to:
- **Console**: Colored, structured output
- **`logs/debug.log`**: All events (50 MB rotation)
- **`logs/error.log`**: Only errors (10 MB rotation)

Access logs:
```bash
tail -f logs/debug.log
tail -f logs/error.log
```

## API Security Considerations

- ✅ Rate limiting (5 concurrent searches)
- ✅ Timeout protection (30s per task)
- ✅ Input validation (Pydantic)
- ✅ Error handling with graceful degradation
- ⚠️ TODO: Add authentication for production
- ⚠️ TODO: Add request rate limiting per IP

## Known Limitations

- LLM API costs scale with research depth
- Tavily API has rate limits (fallback to SerpAPI)
- No long-term memory between sessions
- Single-threaded orchestration (can be improved with Celery)

## Future Enhancements

- [ ] PDF/HTML report generation
- [ ] Vector database for result caching
- [ ] Multi-user sessions with authentication
- [ ] Web UI dashboard
- [ ] Autonomous replanning on failures
- [ ] Result deduplication
- [ ] Citation validation
- [ ] Streaming report generation

## Troubleshooting

### App fails to start
```bash
# Check logs
tail logs/error.log

# Verify env vars
echo $OPENAI_API_KEY
echo $TAVILY_API_KEY
```

### API returns 422 errors
- Verify request format matches schema
- Check `/docs` for field requirements

### Slow research execution
- Increase `TAVILY_MAX_CONCURRENT_SEARCHES`
- Check network connectivity
- Verify API key quotas

## Contributing

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes and test: `pytest`
3. Commit: `git commit -m "Add feature"`
4. Push: `git push origin feature/your-feature`
5. Create pull request

## License

MIT License

## Support

- 📧 Email: support@researchagent.ai
- 🐛 Issues: GitHub Issues
- 💬 Discussions: GitHub Discussions

---

**Built with ❤️ using FastAPI, LangChain, and OpenAI**
