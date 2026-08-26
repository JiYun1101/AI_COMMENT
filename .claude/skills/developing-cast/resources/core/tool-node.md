# ToolNode Implementation

ToolNode is a prebuilt node that executes tool calls from model output. It parses `AIMessage.tool_calls`, runs tools in parallel, and returns `ToolMessage` results.

## Contents

- Import
- Basic Usage
- Error Handling
- Routing with tools_condition
- In a Graph
- ToolNode vs create_agent

## Import

```python
from langgraph.prebuilt import ToolNode, tools_condition
```

## Basic Usage

Define ToolNode in `nodes.py` alongside other nodes:

```python
# casts/{cast_name}/modules/nodes.py
from langgraph.prebuilt import ToolNode
from .tools import search_database, get_weather

# Create ToolNode with tool list
tool_node = ToolNode([search_database, get_weather])
```

ToolNode automatically:
1. Reads the last `AIMessage` from state
2. Parses `tool_calls` from the message
3. Executes each tool call in parallel
4. Returns a list of `ToolMessage` results

---

## Error Handling

```python
# casts/{cast_name}/modules/nodes.py
from langgraph.prebuilt import ToolNode
from .tools import search_database, get_weather

# Graceful error handling — returns error message instead of raising
tool_node = ToolNode(
    [search_database, get_weather],
    handle_tool_errors=True,
)
```

With `handle_tool_errors=True`, failed tool calls return a `ToolMessage` with the error string instead of crashing the graph.

---

## Routing with tools_condition

`tools_condition` routes based on whether the model's response contains tool calls:

```python
from langgraph.prebuilt import tools_condition

# In graph.py — add conditional edge after the model node
builder.add_conditional_edges(
    "model_node",
    tools_condition,
    # "tools" → tool_node, "__end__" → END
)
```

`tools_condition` returns:
- `"tools"` if the last message has `tool_calls`
- `"__end__"` if the model produced a final response

---

## In a Graph

Import `tool_node` from `nodes.py` and `tools_condition` from `langgraph.prebuilt`:

```python
# casts/{cast_name}/graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition
from casts.base_graph import BaseGraph

from casts.{cast_name}.modules.state import State
from casts.{cast_name}.modules.nodes import ModelNode, tool_node

class {CastName}Graph(BaseGraph):
    def build(self):
        builder = StateGraph(self.state)

        builder.add_node("model", ModelNode())
        builder.add_node("tools", tool_node)

        builder.add_edge(START, "model")
        builder.add_conditional_edges(
            "model",
            tools_condition,
        )
        builder.add_edge("tools", "model")

        graph = builder.compile()
        graph.name = self.name
        return graph
```

**Flow:** START → model → (has tool_calls?) → tools → model → ... → END

The model node calls an LLM with `bind_tools(tools)`. If the model requests tools, `tools_condition` routes to the ToolNode. After execution, results return to the model for the next step.

---

## ToolNode vs create_agent

| Aspect | ToolNode | `create_agent` |
|--------|----------|----------------|
| Reasoning loop | No — single pass | Yes — ReAct loop until done |
| Control | You manage the model→tool→model cycle in edges | Self-contained subgraph |
| Flexibility | Full control over routing between model and tools | Encapsulated — opaque reasoning |
| Use when | You need explicit control over the tool execution cycle | You want a self-contained agent with autonomous reasoning |

**Rule:** Use ToolNode when you want explicit graph-level control over the model↔tool cycle. Use `create_agent` when you want the agent to autonomously reason and act.
