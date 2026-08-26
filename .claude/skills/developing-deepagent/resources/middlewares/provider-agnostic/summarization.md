# Summarization

Automatically summarize conversation history when approaching token limits. As of v0.4, summarization occurs in the model node via `wrap_model_call` events, with full message history retained in graph state.

## Basic Usage

```python
# casts.{cast_name}.modules.middlewares
from langchain.agents.middleware import SummarizationMiddleware

def get_summarization_middleware():
    return SummarizationMiddleware(
        model="gpt-4o-mini",           # Model for summarization
        trigger={"tokens": 4000},       # When to trigger
        keep={"messages": 20},          # What to preserve
    )
```

## Auto-trigger via ContextOverflowError (v0.4+)

When no explicit `trigger` is configured, the summarization middleware **auto-triggers** on `ContextOverflowError`. This is supported by `langchain-anthropic` and `langchain-openai`:

- Triggers when context usage reaches **85% of the model's `max_input_tokens`** (from the model profile)
- Retains **10% of tokens** as recent context for continuity
- If no model profile is available, defaults to **170,000 token trigger** or keeps the **last 6 messages**
- On `ContextOverflowError`, the agent automatically falls back to summarization and retries with summary + recent messages

```python
# casts.{cast_name}.modules.middlewares
from langchain.agents.middleware import SummarizationMiddleware

def get_auto_summarization_middleware():
    """Let ContextOverflowError auto-trigger summarization."""
    return SummarizationMiddleware(
        model="claude-haiku-4-5-20251001",
        # No trigger needed — auto-triggers on ContextOverflowError
    )
```

## Explicit Trigger Conditions

Single condition (AND logic) or list of conditions (OR logic):

```python
# Single: trigger if tokens >= 4000 AND messages >= 10
trigger={"tokens": 4000, "messages": 10}

# Multiple: trigger if (tokens >= 5000 AND messages >= 3) OR (tokens >= 3000 AND messages >= 6)
trigger=[
    {"tokens": 5000, "messages": 3},
    {"tokens": 3000, "messages": 6},
]

# Fractional: trigger at 80% of model's context size
trigger={"fraction": 0.8}
```

## Keep Conditions

Specify exactly one:

```python
keep={"messages": 20}    # Keep last 20 messages
keep={"tokens": 2000}    # Keep ~2000 tokens
keep={"fraction": 0.3}   # Keep 30% of context
```

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `model` | Required | Model for generating summaries |
| `trigger` | None | Conditions to trigger. When omitted, auto-triggers on `ContextOverflowError` |
| `keep` | `{messages: 20}` | What to preserve after summarization |
| `summary_prompt` | Built-in | Custom summarization prompt |
| `trim_tokens_to_summarize` | 4000 | Max tokens for summary generation |

## v0.4 Behavior Changes

- Summarization now occurs via `wrap_model_call` events in the model node (not as a separate pre-processing step)
- Full message history is retained in graph state even after summarization
- Token counting accuracy has been enhanced
