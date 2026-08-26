# OpenAI Middleware

## Contents

- Responses API (v0.4+)
- Content Moderation

---

## Responses API (v0.4+)

As of v0.4, OpenAI model strings prefixed with `"openai:"` default to the **Responses API**. New configuration options control data retention and response handling.

### Model String Prefix

```python
# casts.{cast_name}.modules.agents
from deepagents import create_deep_agent

def set_deep_agent():
    return create_deep_agent(
        model="openai:gpt-4.1",  # "openai:" prefix → Responses API by default
        system_prompt="You are a helpful assistant.",
    )
```

### Responses API Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_responses_api` | `bool` | `True` (when `"openai:"` prefix) | Explicitly enable/disable Responses API |
| `store` | `bool` | `True` | Whether to store responses for data retention |
| `include` | `list[str]` | `[]` | Additional response fields to include |

### Disabling Data Retention

```python
# casts.{cast_name}.modules.models
from langchain_openai import ChatOpenAI

def get_openai_model_no_retention():
    """Use Responses API without data retention."""
    return ChatOpenAI(
        model="gpt-4.1",
        use_responses_api=True,
        store=False,
        include=["reasoning.encrypted_content"],
    )
```

### Opting Out of Responses API

```python
# casts.{cast_name}.modules.models
from langchain_openai import ChatOpenAI

def get_openai_model_chat_completions():
    """Force Chat Completions API instead of Responses API."""
    return ChatOpenAI(
        model="gpt-4.1",
        use_responses_api=False,
    )
```

---

## Content Moderation

Moderate agent traffic using OpenAI's moderation endpoint.

```python
# casts.{cast_name}.modules.middlewares
from langchain_openai.middleware import OpenAIModerationMiddleware

def get_openai_moderation_middleware():
    return OpenAIModerationMiddleware(
        model="omni-moderation-latest",
        check_input=True,
        check_output=True,
        exit_behavior="end",
    )
```

```python
# casts.{cast_name}.modules.agents
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from .middlewares import get_openai_moderation_middleware

def set_moderated_agent():
    return create_agent(
        model=ChatOpenAI(model="gpt-4o"),
        tools=[...],
        middleware=[get_openai_moderation_middleware()],
    )
```

## Moderation Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `model` | "omni-moderation-latest" | Moderation model |
| `check_input` | True | Check user messages before model call |
| `check_output` | True | Check AI messages after model call |
| `check_tool_results` | False | Check tool results before model call |
| `exit_behavior` | "end" | `'end'`, `'error'`, or `'replace'` |
| `violation_message` | Built-in | Custom message with `{categories}`, `{category_scores}`, `{original_content}` |

## Exit Behaviors

| Behavior | Description |
|----------|-------------|
| `end` | Stop execution with violation message |
| `error` | Raise `OpenAIModerationError` exception |
| `replace` | Replace flagged content, continue execution |

## Custom Violation Message

```python
# casts.{cast_name}.modules.middlewares
def get_strict_moderation_middleware():
    return OpenAIModerationMiddleware(
        check_input=True,
        check_output=True,
        check_tool_results=True,
        exit_behavior="error",
        violation_message="Policy violation: {categories}. Please rephrase.",
    )
```
