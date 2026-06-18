# context-rag-memory-skills

A framework-free, test-driven Agent Runtime with context assembly, hybrid retrieval, four-type memory system, context pruning and budget reporting, progressive skill activation, and V2 Structured ReAct trajectory tracing.

This repository builds on [agent-runtime-lab](https://github.com/xinglin-li/agent-runtime-lab). It keeps the same core premise: the model can propose text or tool calls, but deterministic runtime code owns state transitions, validation, side effects, trace events, and safety boundaries.

## Project Status

This is an educational runtime lab and prototype, not a production agent platform.

It is designed to make agent mechanics visible and testable:

- V2 Structured ReAct runtime loop with `AgentStep`, `PlannerRationale`, `ToolObservation`, `StopReason`
- trajectory trace with causal event ordering verification
- typed tool calls and validation
- context assembly with pruning, deduplication, and priority-based retention
- `ContextBudgetReport` with utilization tracking and lost-in-the-middle warnings
- BM25 and vector hybrid retrieval with citation formatting
- prompt-injection trust boundaries (`system_trusted` | `retrieved_untrusted` | `user_supplied`)
- four-type memory: Working, Episodic, Semantic, Long-Term
- `WorkingMemory` model for active cognitive state
- `EpisodeRecord` and `MemoryCondenser` for past run compression
- SQLite-backed memory store with namespace isolation and episodic query
- skill discovery and progressive disclosure
- context pruning of stale low-priority items

Requires Python 3.11+. Tested locally with Python 3.12.

## What Changed From The Previous Version

The previous version focused on the runtime core:

- provider adapter boundary
- tool registry allowlist
- Pydantic tool validation
- retry policy
- async execution
- subprocess allowlist
- FastAPI run lifecycle

This version keeps those pieces and adds:

- **V2 Structured ReAct Loop** — `AgentStep` trajectory, `PlannerRationale`, `ToolObservation`, `StopReason`
- **Trajectory Trace Tests** — causal ordering: rationale → action → execution → observation → stop_reason
- **Four-Type Memory System** — Working, Episodic, Semantic, Long-Term
- **`WorkingMemory`** — active cognitive state snapshot (constraints, budget, loop position)
- **`EpisodeRecord` + `MemoryCondenser`** — compact past run snapshots from `AgentState`
- **`ContextPruner`** — stale item removal by age, low-priority overflow cut
- **`ContextBudgetReport`** — structured report with utilization_ratio, trust/kind distributions, lost-in-middle warning
- **Lost-in-the-Middle Mitigation** — positional reordering when >8 items and >90% utilization
- **`ContextAssembler`** upgraded to return `(ContextBundle, ContextBudgetReport)` tuple
- `ContextItem` trust levels: `system_trusted`, `application_trusted`, `user_supplied`, `retrieved_untrusted`
- BM25 lexical retrieval + deterministic fake vector retrieval
- Reciprocal Rank Fusion for hybrid retrieval
- citation map construction for retrieved evidence
- SQLite memory store with namespace isolation, episodic query (`list_episodes_by_namespace`), and upsert semantics
- memory write policy against persistent prompt injection
- `SkillLoader` and `SkillSelector` with progressive disclosure
- progressive skill activation that indexes only skill metadata until a skill is selected
- runtime integration that passes assembled context into the provider as a system message, records `ContextBudgetReport` in trace

## Architecture

```text
==================================================================================================
                         CONTEXT-RAG-MEMORY-SKILLS ARCHITECTURE
==================================================================================================

      [ User Input ]
            |
            v
   +--------------------------+
   |      AgentRuntime        |
   |  run_id / state / trace  |
   |  V2 ReAct loop           |
   |  AgentStep / StopReason  |
   +------------+-------------+
                |
                | pre-model context preparation
                v
   +--------------------------+        +--------------------------+
   |      SkillSelector       |        | HybridRetrievalPipeline  |
   | metadata-only routing    |        | BM25 + vector + RRF      |
   | progressive disclosure   |        | citations + evidence     |
   +------------+-------------+        +------------+-------------+
                |                                   |
                v                                   v
   +--------------------------+        +--------------------------+
   |      SkillLoader         |        | Retrieved Evidence       |
   | load full SKILL.md only  |        | trust=retrieved_untrusted|
   | after activation         |        +--------------------------+
   +------------+-------------+
                |
                v
   +--------------------------+
   | SQLiteMemoryStore        |
   | namespace-scoped memory  |
   | episodic + long-term     |
   +------------+-------------+
                |
                v
   +--------------------------+
   |    Context Control Layer |
   |                          |
   |  deduplicate             |
   |  -> ContextPruner (stale)|
   |  -> priority sort        |
   |  -> budget truncation    |
   |  -> lost-in-middle reord |
   |  -> ContextBudgetReport  |
   +------------+-------------+
                |
                v
   +--------------------------+
   | Provider Input           |
   | system context message   |
   | + conversation history   |
   +------------+-------------+
                |
                v
   +--------------------------+
   | ToolRegistry / Tools     |
   | allowlist + validation   |
   +--------------------------+
```

## Repository Layout

```text
context-rag-memory-skills/
  pyproject.toml
  README.md
  LICENSE
  skills/
    rolling-backtest/
      SKILL.md
      references/checklist.md
    seasonal-diagnostics/
      SKILL.md
  sample_knowledge/
    time_series/
      arima_basics.md
      backtesting.md
  sample_data/
    series/monthly_sales.csv
  scripts/
    safe_describe_csv.py
    safe_series_summary.py
  src/
    agent_runtime/
      api.py
      config.py
      errors.py
      models.py
      tracing.py
      context/
        assembler.py
        budget.py
        dedup.py
        models.py
        pruner.py
      memory/
        condenser.py
        models.py
        policy.py
        sqlite_store.py
        working_memory.py
      providers/
        base.py
        fake_provider.py
      retrieval/
        bm25.py
        chunker.py
        citations.py
        embeddings.py
        hybrid.py
        models.py
        pipeline.py
        reranker.py
        tokenizer.py
        vector_index.py
      runtime/
        async_executor.py
        loop.py
        state.py
        steps.py
      skills/
        loader.py
        models.py
        selector.py
      tools/
        arithmetic.py
        base.py
        idempotency_writer.py
        registry.py
        script_runner.py
  tests/
```

## Quick Start

Install the project in editable mode:

```bash
pip install -e .
pip install pytest pytest-asyncio
```

Run the full test suite:

```bash
pytest -q
```

Expected result at the time of writing:

```text
68 passed
```

Run focused context, retrieval, memory, and skills tests:

```bash
pytest tests/test_context_integration.py tests/test_skill_loader.py tests/test_skill_activation.py -v
```

Run the FastAPI service:

```bash
uvicorn agent_runtime.api:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Core Concepts

### 1. V2 Structured ReAct Runtime

The runtime loop follows a structured ReAct pattern with explicit trajectory models:

```text
observe state
 -> produce PlannerRationale (compact summary, NOT raw CoT)
 -> choose typed ToolAction
 -> validate tool schema
 -> execute deterministic tool
 -> record ToolObservation
 -> build AgentStep (rationale + action + observation)
 -> write StopReason on termination
 -> stop or continue
```

`AgentStep` trajectory is the minimum unit for future eval replay. Causal event ordering is verified by `test_trajectory_trace.py`.

### 2. Four-Type Memory System

The agent distinguishes four memory types explicitly:

| Type | Model | Storage | Lifetime |
|---|---|---|---|
| **Working** | `WorkingMemory` | In-process | Single run |
| **Episodic** | `EpisodeRecord` | SQLite (`memory_type="episodic"`) | Cross-run |
| **Semantic** | RAG chunks, skill metadata | Documents, `skills/` | Persistent |
| **Long-Term** | `MemoryRecord` | SQLite (key-value) | Cross-session |

- **Working Memory** (`WorkingMemory`) — current run constraints, context budget, active skill, loop position. `is_budget_critical()` triggers when utilization >90% with lost-in-middle warning.
- **Episodic Memory** (`EpisodeRecord` + `MemoryCondenser`) — condensed past run snapshot (task summary, key decisions, errors, outcome). Produced from `AgentState` via `MemoryCondenser.condense()`.
- **Semantic Memory** — RAG documents, curated knowledge, skill metadata accessible through retrieval.
- **Long-Term Memory** — cross-session facts, preferences, rules stored in `SQLiteMemoryStore`.

### 3. Context Control Layer

The context assembly pipeline runs in six steps per loop iteration:

1. **Deduplicate** — remove identical content blocks
2. **Prune** — drop stale low-priority items (`age_in_steps > max_age` && `priority < threshold`), then cut low-priority overflow when item count exceeds limit
3. **Sort** — by priority descending
4. **Truncate** — token budget with hard retention for `priority >= 100` system instructions
5. **Reorder** — lost-in-the-middle mitigation: reorder so important items appear at both front and back of the list when >8 items
6. **Report** — produce `ContextBudgetReport` with utilization ratio, trust/kind distributions, and lost-in-middle warning

`ContextAssembler.assemble()` returns `(ContextBundle, ContextBudgetReport)`.

### 4. ContextBudgetReport

Each context assembly produces a structured report:

```python
class ContextBudgetReport:
    total_items_submitted: int
    items_after_dedup: int
    items_pruned: int
    items_dropped_by_budget: int
    items_retained: int
    estimated_tokens_used: int
    max_tokens: int
    utilization_ratio: float
    lost_in_middle_warning: bool
    trust_distribution: dict   # count by trust_level
    kind_distribution: dict    # count by kind
```

The report is recorded in the runtime trace via `model_requested` event payload.

### 5. Trust Levels

Context items carry explicit trust levels:

- `system_trusted`
- `application_trusted`
- `user_supplied`
- `retrieved_untrusted`

Retrieved evidence is passed to the model as data, not instructions. The runtime adds a system instruction that tells the provider to ignore any instruction-like text found in retrieved evidence.

### 6. Hybrid Retrieval

Retrieval uses two deterministic local routes:

- `BM25Retriever` for lexical matching
- `VectorIndex` with `FakeEmbeddingProvider` for stable semantic tests

`ReciprocalRankFusion` combines rankings without assuming comparable score scales. `CitationBuilder` formats evidence blocks and returns a citation map for trace auditing.

### 7. Progressive Skill Activation

Skills live under `skills/*/SKILL.md` with frontmatter metadata:

```yaml
---
name: rolling-backtest
description: Use this skill when evaluating forecasting designs...
allowed_tools: ["run_approved_script"]
---
```

Discovery reads only lightweight metadata. The full skill body is loaded only after `SkillSelector` chooses a matching skill.

This is intentionally different from ordinary RAG over file content. Skill selection is routing, not answer retrieval.

### 8. Long-Term and Episodic Storage

`SQLiteMemoryStore` provides a minimal local memory layer:

- namespace isolation for multi-project multi-tenancy
- lookup by namespace/key with upsert semantics
- episodic query: `list_episodes_by_namespace()` returns recent past run summaries
- `put_episode()` convenience wrapper with memory_type check
- structured `MemoryRecord` and `EpisodeRecord` models

`MemoryWritePolicy` rejects persistent prompt-injection-like content before it reaches storage.

### 9. Memory Condensation

`MemoryCondenser` converts a complete `AgentState` into a compact `EpisodeRecord`:

- extracts user query as task summary
- maps agent status to outcome (`completed`/`failed`/`cancelled`/`max_steps_exceeded`)
- captures key decisions from each `AgentStep.action + rationale`
- extracts error messages from failed `ToolObservation`s
- discards raw message history

### 10. Runtime Integration

Before calling the provider, `AgentRuntime`:

1. Activates matching skill via `SkillSelector`
2. Executes `HybridRetrievalPipeline`
3. Loads namespace memories from `SQLiteMemoryStore`
4. Assembles context via `ContextAssembler` (pruning + budget + lost-in-middle)
5. Records `ContextBudgetReport` in trace (utilization, dropped, pruned)
6. Passes context as system message + conversation history to provider
7. Runs V2 Structured ReAct loop with `AgentStep` construction

## Test Matrix

| Area | Coverage |
| --- | --- |
| Runtime loop | direct answer, tool call, max steps, V2 trajectory assertions |
| Trajectory trace | AgentStep structure, causal event ordering, no raw CoT, StopReason |
| Registry | allowlist, duplicate registration, schema listing |
| Validation | invalid types, missing args, business boundary, unknown tool |
| Error policy | transient retry self-healing, fatal unknown-tool stop |
| Async executor | concurrency, timeout, idempotency |
| Script runner | approved scripts, path traversal, timeout |
| Retrieval | tokenizer, BM25, vector index, RRF, citations, insufficient evidence |
| Context | deduplication, priority ordering, budget dropping, system retention |
| Context pruning | stale item removal, trust/kind distributions, lost-in-middle warning |
| Episodic memory | condensation, key decisions, error extraction, roundtrip, SQLite CRUD |
| Working memory | defaults, remaining_steps, budget_critical, snapshot |
| Memory policy | injection attack detection, namespace isolation, upsert |
| Skills | metadata discovery, activation, fuzzy selection, progressive disclosure |
| Integration | RAG + skill fusion, adversarial prompt-injection immunization |
| API | health check, run submission, polling, trace fetch, 404 boundary |

Run all tests:

```bash
pytest -v
```

Run one test file:

```bash
pytest tests/test_context_pruning.py -v
```

Run one test:

```bash
pytest tests/test_working_memory.py::test_budget_critical_when_high_utilization -v
```

## Security Notice

This project demonstrates application-level safety controls:

- tool allowlists
- Pydantic validation
- structured runtime errors
- context trust levels
- retrieved-evidence instruction boundaries
- memory write filtering
- context pruning and budget control
- approved subprocess scripts
- path checks
- hard subprocess timeout

It is not a secure sandbox.

Do not run untrusted scripts through this project. Do not expose the FastAPI service directly to the public internet. Do not treat the subprocess runner as an isolation boundary. Production-grade execution of untrusted code requires operating-system-level isolation such as containers, cgroups, seccomp, gVisor, Firecracker, separate users, filesystem restrictions, CPU and memory quotas, and network egress controls.

## Known Limitations

- The vector index uses deterministic fake embeddings for tests, not production embeddings.
- SQLite memory is local and minimal.
- The API uses in-memory run tracking.
- `WorkingMemory` is built at run start but not yet auto-populated from the runtime loop in all paths.
- `EpisodeRecord` condensation is available as a library call; auto-condensation on run completion is future work.
- Skill selection indexes metadata only; skill-local reference retrieval is future work.
- Context token estimation is approximate.
- The prompt-injection defense is an application-level boundary, not a formal security proof.
- Provider integration is represented by `FakeProvider`; real model adapters are future work.
- The subprocess runner is allowlisted but not OS-sandboxed.

## Future Work

Potential next steps:

- real embedding provider adapters
- persistent run store
- auto-condensation: emit `EpisodeRecord` on every run completion
- `WorkingMemory` population from runtime loop on each iteration
- skill-scoped reference retrieval after activation
- provider adapters for OpenAI-compatible APIs and local models
- streaming responses
- richer memory ranking and decay policy
- context compaction and summarization
- MCP-compatible tool registration
- OS-level sandboxing for subprocess tools
- golden dataset evaluation for retrieval and skill activation
- trajectory replay and evaluation from persisted AgentStep sequences

## Design Summary

The model is probabilistic. The runtime is deterministic.

This project demonstrates a compact control plane for wrapping model behavior in explicit software boundaries: typed messages, schema-validated tools, registry allowlists, bounded loops, structured errors, trace events, retrieval trust levels, four-type memory, context pruning and budget reporting, episodic condensation, working memory models, and progressive skill activation.

That is the core engineering move: let the model propose actions, but let deterministic runtime code decide what is allowed to happen, what context it sees, and what gets remembered.

## License

MIT License. See [LICENSE](LICENSE).