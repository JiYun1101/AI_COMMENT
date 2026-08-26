# Mode 4: Redesign Cast Questions

Use when implementation code exists and user wants to redesign architecture.

---

## Context Analysis (Before Asking)

**First, analyze existing implementation:**
1. Read `graph.py` → Discover current nodes, edges, patterns
2. Read `modules/nodes.py` → Understand node responsibilities
3. Read `modules/agents.py` (if exists) → Discover agent subgraphs
4. Read `modules/state.py` → Understand current state shape
5. Read `modules/conditions.py` (if exists) → Understand routing logic
6. Read `CLAUDE.md` (if exists) → Compare spec vs implementation

**Present summary before asking questions.**

---

## Questions (Ask Only If Needed)

### Q1: Redesign Scope

**Condition**:
- Always ask: Need to understand what the user wants to change

**AskUserQuestion Format**:
```json
{
  "question": "What aspects of the current architecture need redesign?",
  "header": "Redesign Scope",
  "options": [
    {"label": "Overall pattern change", "description": "Change workflow pattern (e.g., Sequential → Coordinator)"},
    {"label": "Add/remove/modify nodes", "description": "Change specific nodes or their responsibilities"},
    {"label": "Change node composition", "description": "Convert flat nodes to agent subgraphs or vice versa"},
    {"label": "Restructure routing/edges", "description": "Change how nodes connect and route"},
    {"label": "Full redesign", "description": "Rethink the entire cast architecture from scratch"}
  ],
  "multiSelect": true
}
```

---

### Q2: Constraints

**Condition**:
- Skip if: User already specified constraints
- Required when: Redesign scope is broad (pattern change or full redesign)

**AskUserQuestion Format**:
```json
{
  "question": "Are there constraints for the redesign?",
  "header": "Redesign Constraints",
  "options": [
    {"label": "Preserve existing interfaces", "description": "Keep current input/output contract unchanged"},
    {"label": "Backward compatible", "description": "Existing callers should still work"},
    {"label": "Minimize changes", "description": "Change as little as possible to achieve goal"},
    {"label": "No constraints", "description": "Free to redesign completely"}
  ],
  "multiSelect": true
}
```

---

### Q3: Migration Preference

**Condition**:
- Always ask: Affects how CLAUDE.md is generated

**AskUserQuestion Format**:
```json
{
  "question": "How should the CLAUDE.md reflect the redesign?",
  "header": "Migration",
  "options": [
    {"label": "Update to match current code", "description": "Sync CLAUDE.md with what's already implemented"},
    {"label": "Redesign as new target", "description": "Write new architecture spec, implementation will follow"},
    {"label": "Both: document current + propose changes", "description": "Show current state and proposed redesign"}
  ],
  "multiSelect": false
}
```

---

## After Questions: Summarize

**Template:**
```
"Here's the redesign plan:

**Current Architecture:**
- **Pattern:** [current pattern]
- **Nodes:** [current node list with types]

**Proposed Changes:**
- [change 1]
- [change 2]
- ...

**Constraints:** [constraints]

Shall I proceed with the redesign?"
```

**Wait for confirmation before proceeding to Cast Design Workflow.**
