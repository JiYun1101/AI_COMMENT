# AsyncSubAgent

Launch non-blocking background subagents that execute concurrently while the main agent continues.

## Contents

- Overview
- Parameters
- ASGI Transport (Co-deployed)
- HTTP Transport (Remote)
- Passing to create_deep_agent
- Requirements
- When to Use / NOT to Use

## Overview

- Subagents run as **non-blocking background tasks**
- Main agent continues interacting with the user while subagents work
- Results are delivered asynchronously when subagents finish
- **Requires LangSmith Deployment** for full functionality

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | Yes | Unique identifier for the subagent |
| `description` | `str` | Yes | What it does (main agent uses this to decide delegation) |
| `graph_id` | `str` | Yes | ID of the deployed graph to run |
| `url` | `str` | No | Remote deployment URL. Omit for ASGI transport (co-deployed) |

## ASGI Transport (Co-deployed)

When subagent graphs are deployed in the same LangSmith Deployment, omit `url` to use in-process ASGI transport:

```python
# casts.{cast_name}.modules.agents
from deepagents import AsyncSubAgent, create_deep_agent
from .models import get_deep_agent_model

def get_async_subagents():
    return [
        AsyncSubAgent(
            name="researcher",
            description="Research agent for information gathering and synthesis",
            graph_id="researcher",
            # No url → ASGI transport (co-deployed in the same deployment)
        ),
        AsyncSubAgent(
            name="coder",
            description="Coding agent for code generation and review",
            graph_id="coder",
        ),
    ]

def set_deep_agent():
    return create_deep_agent(
        model=get_deep_agent_model(),
        subagents=get_async_subagents(),
    )
```

## HTTP Transport (Remote)

For subagent graphs deployed on a different LangSmith Deployment, provide the `url`:

```python
# casts.{cast_name}.modules.agents
from deepagents import AsyncSubAgent

def get_remote_async_subagents():
    return [
        AsyncSubAgent(
            name="coder",
            description="Coding agent for code generation and review",
            graph_id="coder",
            url="https://coder-deployment.langsmith.dev",
        ),
    ]
```

## Passing to create_deep_agent

Async subagents can be mixed with regular (dict, CompiledSubAgent) subagents:

```python
# casts.{cast_name}.modules.agents
from deepagents import AsyncSubAgent, create_deep_agent

def set_deep_agent():
    return create_deep_agent(
        model=get_deep_agent_model(),
        subagents=[
            AsyncSubAgent(
                name="researcher",
                description="Background research",
                graph_id="researcher",
            ),
            {
                "name": "writer",
                "description": "Inline report writing",
                "system_prompt": "You are a technical writer.",
                "tools": [],
            },
        ],
    )
```

## Requirements

- **LangSmith Deployment** is required for async subagent execution
- The `graph_id` must correspond to a deployed graph in the target deployment
- ASGI transport (no `url`) requires co-deployment in the same deployment

## When to Use

- Long-running background tasks (research, data processing) that shouldn't block the user
- Multiple independent tasks that benefit from concurrent execution
- Cross-deployment agent orchestration (via HTTP transport)

## When NOT to Use

- Subagent result is needed immediately before proceeding -> use dict-based or CompiledSubAgent
- Local development without LangSmith Deployment -> use synchronous subagents
- Simple context isolation -> use the general-purpose subagent
