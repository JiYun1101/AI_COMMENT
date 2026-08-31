# LLM provider selection

The recommendation pipeline keeps deterministic context collection, safety filtering, and ranking unchanged. Only candidate generation is provider-selectable.

## Selection order

1. If both `OPENAI_API_KEY` and `OPENAI_MODEL` are non-empty, the existing OpenAI Responses API client is used.
2. Otherwise the app reads the generic `LLM_*` fallback variables.
3. The supported fallback provider is currently `gemini`.

This means existing OpenAI configuration remains backward compatible. To test Gemini without deleting values permanently, leave the OpenAI key/model empty in `.env.local` and configure the fallback block.

```env
# OpenAI takes priority when both are set.
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_BASE_URL=https://api.openai.com/v1

# Fallback used when OpenAI is not fully configured.
LLM_PROVIDER=gemini
LLM_API_KEY=
LLM_MODEL=gemini-3.7-flash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta2
LLM_THINKING_LEVEL=medium
```

`YOUTUBE_API_KEY` is separate from `LLM_API_KEY`. Do not reuse or expose either key.

## Why Gemini 3.7 Flash

As of 2026-08-31, Gemini 3.7 Flash is a GA production model released in August 2026. Google describes it as its most intelligent workhorse Flash model, with a 1M-token context window and configurable `low`, `medium`, and `high` thinking levels. The app defaults to `medium` as a quality/latency balance for generating many short comment candidates.

The fallback client uses Google's Interactions API rather than the legacy `generateContent` API and requests structured JSON output matching the existing candidate schema.

## Health check

`GET /health` exposes the selected provider:

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

When OpenAI is configured, `selection` becomes `openai` and `provider` becomes `openai_responses_api`.
