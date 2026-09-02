# LLM provider selection

The recommendation pipeline keeps deterministic context collection, safety filtering, and reaction ranking unchanged. Only candidate generation is provider-selectable.

## Selection order

1. If both `OPENAI_API_KEY` and `OPENAI_MODEL` are non-empty, the existing OpenAI Responses API client is used.
2. Otherwise the app reads the generic `LLM_*` fallback configuration.
3. If `LLM_PROVIDER` is empty, the default fallback is **local Ollama**.
4. Gemini remains available by explicitly setting `LLM_PROVIDER=gemini`.

The app does not automatically switch providers after a runtime OpenAI error. For example, an OpenAI 429/5xx response is returned as an error rather than silently retrying through Ollama or Gemini.

## Default: local Ollama + Qwen3 8B

Ollama runs the model on the user's machine, so no external LLM API key or per-request provider billing is required.

Install Ollama, then download the default model once:

```bash
ollama pull qwen3:8b
```

Make sure the Ollama service is running. The default local endpoint is:

```text
http://localhost:11434
```

Fallback environment variables:

```env
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_BASE_URL=https://api.openai.com/v1

LLM_PROVIDER=ollama
LLM_API_KEY=
LLM_MODEL=qwen3:8b
LLM_BASE_URL=http://localhost:11434
```

`LLM_API_KEY` is intentionally empty for Ollama.

The implementation calls Ollama's native `POST /api/chat` endpoint with:

- `stream: false`
- `think: false`
- a JSON Schema in `format`

This keeps Qwen3's reasoning output out of the final candidate payload and asks Ollama to return the same `{ "candidates": [...] }` contract used by the rest of the application.

Current local client:

```text
src/recommender/candidate_generator.py
        ↓
src/llm/provider.py
        ↓
src/llm/ollama_client.py
        ↓ HTTP POST
http://localhost:11434/api/chat
```

## Optional Gemini provider

Gemini is still supported as an external fallback provider when explicitly selected:

```env
OPENAI_API_KEY=
OPENAI_MODEL=

LLM_PROVIDER=gemini
LLM_API_KEY=your_gemini_api_key
LLM_MODEL=gemini-3.7-flash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta2
LLM_THINKING_LEVEL=medium
```

`YOUTUBE_API_KEY` and `LLM_API_KEY` are separate keys. Neither is used by local Ollama.

## OpenAI priority

Existing OpenAI configuration remains backward compatible:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=your_selected_model
OPENAI_BASE_URL=https://api.openai.com/v1
```

When both OpenAI values are present, `LLM_PROVIDER` is ignored for candidate generation and OpenAI is selected.

## Health check

OpenAI example:

```json
{
  "llm": {
    "ready": true,
    "provider": "openai_responses_api",
    "selection": "openai",
    "model": "<OPENAI_MODEL>",
    "missing": []
  }
}
```

Default Ollama example:

```json
{
  "llm": {
    "ready": true,
    "provider": "ollama_local",
    "selection": "fallback",
    "model": "qwen3:8b",
    "missing": []
  }
}
```

Gemini example:

```json
{
  "llm": {
    "ready": true,
    "provider": "gemini_interactions_api",
    "selection": "fallback",
    "model": "gemini-3.7-flash",
    "missing": []
  }
}
```

For Ollama, `ready: true` means the local provider is configured with a model name. `/health` does not load the model or continuously probe the local Ollama process. If Ollama is not running, `/recommend` returns a local-LLM connection error.
