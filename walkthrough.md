# Fix LLM Provider Catalog Discovery & Connection Testing — Walkthrough

## Summary

### Root Cause
In commit `8e4d466` / `007ed62`, a top-level import was added to `backend/app/presentation/api/v1/learning.py`:
```python
from app.main import ai_service_bus  # noqa: E402
```
When `app.main` starts loading, it imports `learning_router` at line 19 **before** `ai_service_bus` is created on line 104 in `app.main`. This created a top-level circular dependency resulting in an immediate boot crash:
`ImportError: cannot import name 'ai_service_bus' from partially initialized module 'app.main'`

Because the backend server failed to boot, all frontend API calls (such as `GET /api/v1/settings/providers/catalog` and `POST /api/v1/settings/providers/{provider}/test`) failed with `Failed to fetch` network errors.

### Solution Applied
- **Removed Circular Import**: Removed `from app.main import ai_service_bus` from `learning.py`.
- **Clean Setter Injection**: Added `set_ai_service_bus(ai_bus)` in `learning.py` to update the module-level `flashcard_service`, `quiz_service`, and `_analytics` singletons when initialized by `main.py`.
- **Composition Root Injection**: In `main.py`, invoked `set_learning_ai_service_bus(ai_service_bus)` immediately after initializing `ai_service_bus`.
- **Zero Reverse Dependencies**: `learning.py`, `flashcard_service.py`, and `quiz_service.py` have zero dependencies back on `app.main`.

---

## Changed Files

| File | Changes |
| :--- | :--- |
| [`backend/app/presentation/api/v1/learning.py`](file:///e:/repos/athenus/backend/app/presentation/api/v1/learning.py) | Removed top-level import of `ai_service_bus` from `app.main`. Added `set_ai_service_bus(ai_bus)` setter function. |
| [`backend/app/main.py`](file:///e:/repos/athenus/backend/app/main.py) | Added call to `set_learning_ai_service_bus(ai_service_bus)` after instantiating `ai_service_bus`. |

---

## Manual Verification Matrix

| Step | Check | Command / Action | Result | Notes |
| :---: | :--- | :--- | :---: | :--- |
| **1** | **Python Module Import Test** | `python -c "import app.main; print('Backend import OK')"` | **PASS** | Imported cleanly without circular import errors. |
| **2** | **Full Pytest Suite** | `python -m pytest` | **PASS** | 121/121 test cases passed across all backend test modules. |
| **3** | **Backend Server Boot** | `python -m uvicorn app.main:app --port 8000` | **PASS** | Backend booted cleanly with `Application startup complete.` |
| **4** | **Provider Catalog Discovery** | `curl.exe -fsS http://localhost:8000/api/v1/settings/providers/catalog` | **PASS** | Returns full catalog for `ollama`, `groq`, `openrouter`, `openai`, `anthropic`. |
| **5.1** | **Ollama Connection Test** | `curl.exe -X POST http://localhost:8000/api/v1/settings/providers/ollama/test` | **PASS** | `{"is_available":true,"is_configured":true,"active_model":"llama3:8b"}` |
| **5.2** | **Groq Connection Test** | `curl.exe -X POST http://localhost:8000/api/v1/settings/providers/groq/test` | **PASS** | `{"is_available":true,"is_configured":true,"active_model":"llama-3.3-70b-versatile"}` |
| **5.3** | **OpenRouter Connection Test** | `curl.exe -X POST http://localhost:8000/api/v1/settings/providers/openrouter/test` | **PASS** | `{"is_available":true,"is_configured":true,"active_model":"google/gemini-2.5-flash"}` |
| **5.4** | **OpenAI Connection Test** | `curl.exe -X POST http://localhost:8000/api/v1/settings/providers/openai/test` | **PASS** | `{"is_available":false,"is_configured":false,"error":"Missing API key in .env"}` |
| **5.5** | **Anthropic Connection Test** | `curl.exe -X POST http://localhost:8000/api/v1/settings/providers/anthropic/test` | **PASS** | `{"is_available":false,"is_configured":false,"error":"Missing API key in .env"}` |
| **6.1** | **Quiz Generation Endpoint** | `curl.exe -X POST http://localhost:8000/api/v1/learning/quizzes/default/generate` | **PASS** | `{"id":"quiz_default_v2","status":"ready"}` |
| **6.2** | **Flashcard Deck Generation Endpoint** | `curl.exe -X POST http://localhost:8000/api/v1/learning/decks/default` | **PASS** | `{"id":"deck_default_v1","status":"ready","card_count":16}` |
