# Node Specification Guide

## Core Principle

**Single Responsibility:** Each node does ONE thing.

**Test:** If you use "and" to describe it, split it.

## Design Process

1. Break workflow into discrete operations
2. Each LLM/API/DB call = separate node
3. Apply granularity check

**Too coarse (split):** Does multiple operations, hard to describe in one sentence.

**Too fine (merge):** Always runs together, trivial operation.

## Node Types

### 1. Built-in Virtual Nodes (`START`, `END`)

Flow control markers from `langgraph.graph`. `START` is the entry point of every graph; `END` terminates a branch. These are not user-defined — they are structural constants used in edge definitions.

- `START` → first node edge is required
- All execution paths must reach `END`
- Never add logic to START/END — they are routing markers only

### 2. ToolNode (`langgraph.prebuilt`)

A prebuilt node that parses `AIMessage.tool_calls`, executes tools in parallel, and returns a list of `ToolMessage` results. Use when a model's tool calls need to be executed without a full agent reasoning loop.

- Pairs with `tools_condition` for routing (has tool calls → ToolNode, else → END)
- Supports `handle_tool_errors=True` for graceful error handling
- Stateless execution — no reasoning loop, no memory

### 3. `create_agent` Subgraph

A `create_agent` compiled graph added as a node or invoked inside a node. Has its own tool set and ReAct reasoning loop. Use when the node needs tools + autonomous reasoning.

- Returns `CompiledGraph` — can be added as subgraph node (shared state) or called inside a node (different state)
- Self-contained reasoning: model → tool calls → observation → repeat until done

### 4. `create_deep_agent` Subgraph

A `create_deep_agent` compiled graph. Has built-in planning (`write_todos`), subagent delegation, pluggable backends, and long-term memory. Use when the node needs multi-step planning, sandbox execution, or subagent spawning.

- Contains `create_agent` internally — superset of agent capabilities
- Can be added as subgraph node or called inside a node

### 5. Custom Node (`BaseNode` / `AsyncBaseNode`)

A user-defined node extending `BaseNode` (sync) or `AsyncBaseNode` (async) from `casts/base_node.py`. Single deterministic operation — reads state, returns partial update dict.

- Must implement `execute(self, state, ...)` method
- Optional parameters: `config` (RunnableConfig), `runtime` (Runtime)
- No internal reasoning loop — explicit, predictable logic

## Output Format

**IMPORTANT: Describe node structure only. Do NOT write other modules (tool, middleware etc.) or implementation code (def functions, classes etc.).**

For **virtual nodes** (START/END):
```
Edges:
- START → FirstNodeName
- LastNodeName → END
```

For **ToolNode**:
```
Nodes:
- ToolExecutor (ToolNode) - Execute tool calls from model output
  - Tools: [tool names]
  - Routing: tools_condition (has_tool_calls → ToolExecutor, else → END)
```

For **custom nodes** (BaseNode/AsyncBaseNode):
```
Nodes:
- NodeName - Single responsibility description
```

For **agent subgraph nodes**:
```
Nodes:
- AgentName (create_agent subgraph) - Agent responsibility description
  - Tools: [tool names]
```

For **deep agent subgraph nodes**:
```
Nodes:
- AgentName (create_deep_agent) - Agent responsibility description
  - Tools: [tool names]
```

## Naming Convention

**REQUIRED: CamelCase format** (not lowercase or snake_case)
- ✅ Good: `InspectorAgent`, `ResponseGenerator`, `ToolExecutor`
- ❌ Bad: `inspect_agent`, `generate_response`, `tool_executor`

## Checklist

- [ ] START → first node edge defined
- [ ] All execution paths reach END
- [ ] Each node has single responsibility
- [ ] Names are clear (VerbNoun format)
- [ ] LLM calls are separated
- [ ] ToolNode used for stateless tool execution (not full agent)
- [ ] create_agent used only when reasoning loop needed
