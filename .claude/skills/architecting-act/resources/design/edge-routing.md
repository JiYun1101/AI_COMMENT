# Architecture Diagram Guide

Guide for creating clear Mermaid diagrams that represent your Cast architecture.

## Design Process

1. Start with START node
2. Add nodes based on selected pattern
3. Connect nodes with edges (normal or conditional)
4. Ensure all paths reach END
5. Add exit conditions for loops

## Mermaid Syntax

### Basic Structure
```mermaid
graph LR
    START([START]) --> A[ProcessNode]
    A --> END([END])
```

### Conditional Routing
```mermaid
graph LR
    START([START]) --> A{RouteDecision}
    A -->|condition_a| B[PrimaryNode]
    A -->|condition_b| C[SecondaryNode]
    A -->|default| D[FallbackNode]
    B --> END([END])
    C --> END([END])
    D --> END([END])
```

### Loops
```mermaid
graph LR
    START([START]) --> A[ProcessNode]
    A --> B{EvaluateResultNode}
    B -->|pass| END([END])
    B -->|fail| C[RefineNode]
    C --> A
```

## Node Shapes

| Node Type | Description | Mermaid Syntax |
|-----------|-------------|----------------|
| **START/END** | Main-Graph initial start/final end. Use an Internal Connector if it serves as an entry point for a subgraph. | `([START])`, `([END])` |
| **Process Node** | Core function/feature nodes in the graph | `[Node Name]` |
| **Condition / Route Function** | Decision point when internal events or triggers occur - Router, Branch out, IF Function, etc | `{Condition / Route Function Name}` |
| **Agent Subgraph** | A `create_agent` or `create_deep_agent` subgraph used as a node | `subgraph Name["Label (subgraph)"]` |
| **Subgraph Entry/Exit** | Internal connectors for subgraph boundaries | `([entry])`, `([exit])` |
| **Internal Invocation** | A node internally invoking a subgraph (Strategy B) | `-.->` (dotted arrow) |

### Agent Subgraph as Node (Strategy A)
```mermaid
graph LR
    START([START]) --> A[PreprocessNode]
    A --> B

    subgraph B["AgentName (create_agent subgraph)"]
        direction LR
        B1([entry]) --> B2[ReasonNode]
        B2 --> B3[ToolCallNode]
        B3 --> B4{ShouldContinue}
        B4 -->|yes| B2
        B4 -->|no| B5([exit])
    end

    B --> C[PostprocessNode]
    C --> END([END])
```

### Node Internally Invoking Subgraph (Strategy B)
```mermaid
graph LR
    START([START]) --> A[OrchestratorNode]
    A -.->|internally invokes| B["AgentAlpha (subgraph)"]
    A -.->|internally invokes| C["AgentBeta (subgraph)"]
    A --> D[ResultNode]
    D --> END([END])
```

### DeepAgent with CompiledSubAgent (Strategy D)
```mermaid
graph LR
    START([START]) --> A

    subgraph A["MainAgent (create_deep_agent)"]
        direction LR
        A1([entry]) --> A2[PlanNode]
        A2 --> A3{Delegate}
        A3 -->|task_a| A4["SubAgentA (CompiledSubAgent)"]
        A3 -->|task_b| A5["SubAgentB (CompiledSubAgent)"]
        A4 --> A6[SynthesizeNode]
        A5 --> A6
        A6 --> A7([exit])
    end

    A --> END([END])
```

## Design Principles

**Clarity:** Each node should be clearly labeled with CamelCase names

**Completeness:** All paths must reach END

**Loops:** Must show exit condition and loop path

**Conditionals:** Label edges with conditions (e.g., `|condition|`)

## Checklist

- [ ] START node present
- [ ] All nodes connected
- [ ] All paths reach END
- [ ] Conditional edges labeled with conditions
- [ ] Loop exit conditions shown
- [ ] Node names use CamelCase