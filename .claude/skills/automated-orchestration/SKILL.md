---
name: automated-orchestration
description: Use when building multi-stage analysis pipelines that need checkpoint/resume, when long-running jobs fail mid-execution and lose progress, when processing large data archives that exceed memory or rate limits, or when analysis depth should adapt to data volume
---

# Automated Orchestration with Checkpoints

## Overview

Coordinate end-to-end analytical pipelines with checkpoint/resume capabilities and activity-based depth adjustment. The core principle: **every stage that can fail must be resumable, and every pipeline must adapt its depth to the data it encounters.**

## When to Use

- Pipeline processes multiple stages sequentially and failures lose hours of work
- Large data corpus requires chunked processing with rate-limit awareness
- Analysis depth should scale with data volume (shallow scan vs. deep dive)
- Long-running jobs need graceful interruption and restart
- Multiple data sources must be combined across stages with partial-failure tolerance

**When NOT to use:**
- Single-shot scripts under 5 minutes with no intermediate state
- Pipelines where full re-execution is cheap and acceptable
- Real-time streaming (use event-driven patterns instead)

## Core Pattern

```
WITHOUT orchestration:          WITH orchestration:

fetch_all_data()       -->      Stage 1: fetch  [checkpoint] -->
process_everything()   -->      Stage 2: parse  [checkpoint] -->
analyze_all()          -->      Stage 3: enrich [checkpoint] -->
generate_report()               Stage 4: report [checkpoint]

Fails at analyze?               Fails at enrich?
Start over from scratch.        Resume from Stage 3 checkpoint.
```

## Quick Reference

| Concept | Pattern | Anti-pattern |
|---------|---------|-------------|
| **Checkpointing** | JSON/pickle per stage, atomic writes | No checkpoints on jobs > 5 min |
| **Idempotency** | Delete-then-write, upsert by key | Append-only without dedup |
| **Depth adjustment** | Scale analysis tiers to item count | Hardcoded depth for all inputs |
| **Rate limits** | Exponential backoff with jitter | Retry loops without delay |
| **Progress** | Structured log per stage with counts | Silent processing, no visibility |
| **Failure handling** | Isolate stages, continue on partial | Abort entire pipeline on one error |

## Pipeline Architecture

### 1. Define stages as idempotent units

Each stage reads an input artifact, produces an output artifact, and writes a checkpoint on success. Re-running a completed stage is a no-op.

```python
import json, os, time, hashlib
from pathlib import Path

class PipelineStage:
    """Base for an idempotent, checkpointed pipeline stage."""

    def __init__(self, name, checkpoint_dir="checkpoints"):
        self.name = name
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    @property
    def checkpoint_path(self):
        return self.checkpoint_dir / f"{self.name}.json"

    def is_complete(self):
        """Check if this stage already finished successfully."""
        if not self.checkpoint_path.exists():
            return False
        cp = json.loads(self.checkpoint_path.read_text())
        return cp.get("status") == "complete"

    def load_checkpoint(self):
        """Load partial progress for resume."""
        if self.checkpoint_path.exists():
            return json.loads(self.checkpoint_path.read_text())
        return {"status": "not_started", "processed": [], "errors": []}

    def save_checkpoint(self, state):
        """Atomic checkpoint write: write tmp then rename."""
        tmp = self.checkpoint_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, default=str))
        tmp.rename(self.checkpoint_path)  # atomic on POSIX

    def run(self, input_data):
        """Execute stage with checkpoint/resume logic."""
        if self.is_complete():
            print(f"[{self.name}] Already complete, skipping.")
            return self._load_output()

        state = self.load_checkpoint()
        already_done = set(state.get("processed", []))
        items = [i for i in input_data if self._item_key(i) not in already_done]

        print(f"[{self.name}] Processing {len(items)} items "
              f"({len(already_done)} already done)")

        for i, item in enumerate(items):
            try:
                result = self.process_item(item)
                state["processed"].append(self._item_key(item))
                # Checkpoint every N items for large batches
                if (i + 1) % self.checkpoint_interval == 0:
                    self.save_checkpoint(state)
            except Exception as e:
                state["errors"].append({
                    "item": self._item_key(item),
                    "error": str(e), "time": time.time()
                })
                self.save_checkpoint(state)
                # Continue processing; don't abort the whole stage
                continue

        state["status"] = "complete"
        state["completed_at"] = time.time()
        self.save_checkpoint(state)
        return self._load_output()

    # Override these in subclasses
    def process_item(self, item):
        raise NotImplementedError

    def _item_key(self, item):
        """Unique key for deduplication."""
        return hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest()

    def _load_output(self):
        """Load this stage's output artifact."""
        raise NotImplementedError

    checkpoint_interval = 50  # save checkpoint every N items
```

### 2. Orchestrate stages with a pipeline runner

```python
class Pipeline:
    """Run stages in sequence with checkpoint awareness."""

    def __init__(self, stages, checkpoint_dir="checkpoints"):
        self.stages = stages
        self.checkpoint_dir = Path(checkpoint_dir)
        self.log = []

    def run(self, initial_input):
        data = initial_input
        for stage in self.stages:
            t0 = time.time()
            try:
                data = stage.run(data)
                elapsed = time.time() - t0
                self.log.append({
                    "stage": stage.name, "status": "complete",
                    "elapsed_s": round(elapsed, 1),
                    "items": len(stage.load_checkpoint().get("processed", [])),
                    "errors": len(stage.load_checkpoint().get("errors", []))
                })
            except KeyboardInterrupt:
                self.log.append({"stage": stage.name, "status": "interrupted"})
                print(f"\n[pipeline] Interrupted at {stage.name}. "
                      f"Re-run to resume from this stage.")
                break
            except Exception as e:
                self.log.append({
                    "stage": stage.name, "status": "failed", "error": str(e)
                })
                print(f"[pipeline] Stage {stage.name} failed: {e}")
                break
        return data

    def write_report(self, path="docs/analysis/03-automated-orchestration.md"):
        """Write pipeline status report."""
        report = self._build_report()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(report)

    def _build_report(self):
        lines = ["# Automated Orchestration Report\n"]
        lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("## Pipeline Status\n")
        lines.append("| Stage | Status | Items | Errors | Time (s) |")
        lines.append("|-------|--------|-------|--------|----------|")
        for entry in self.log:
            lines.append(
                f"| {entry.get('stage','')} "
                f"| {entry.get('status','')} "
                f"| {entry.get('items','-')} "
                f"| {entry.get('errors','-')} "
                f"| {entry.get('elapsed_s','-')} |"
            )
        # Summarize interruptions / skips
        failures = [e for e in self.log if e["status"] != "complete"]
        if failures:
            lines.append("\n## Interruptions and Failures\n")
            for f in failures:
                lines.append(f"- **{f['stage']}**: {f['status']}"
                             + (f" -- {f['error']}" if "error" in f else ""))
        else:
            lines.append("\n## Result\n")
            lines.append("All stages completed successfully.")
        return "\n".join(lines) + "\n"
```

### 3. Activity-based depth adjustment

Scale analysis intensity to data volume. Avoid spending deep-analysis resources on tiny datasets, or shallow-scanning massive ones without prioritization.

```python
def choose_depth(item_count, thresholds=None):
    """Select analysis depth tier based on item count.

    Returns a dict of parameters that downstream stages consume.
    Callers should NOT hardcode depth -- always derive from data.
    """
    thresholds = thresholds or {
        "shallow":  (0, 100),      # quick summary only
        "standard": (101, 5000),   # full analysis per item
        "deep":     (5001, 50000), # sampled deep + full summary
        "archival": (50001, None), # statistical sampling + key items only
    }
    for tier, (lo, hi) in thresholds.items():
        if hi is None and item_count >= lo:
            return {"tier": tier, "sample_rate": 0.05, "full_analysis": False}
        if lo <= item_count <= hi:
            return {"tier": tier,
                    "sample_rate": 1.0 if tier in ("shallow","standard") else 0.2,
                    "full_analysis": tier in ("shallow", "standard")}
    return {"tier": "standard", "sample_rate": 1.0, "full_analysis": True}
```

### 4. Rate-limit-aware fetching

```python
import random

def fetch_with_backoff(fetch_fn, max_retries=5, base_delay=1.0):
    """Retry with exponential backoff + jitter. Respects rate limits."""
    for attempt in range(max_retries):
        try:
            return fetch_fn()
        except RateLimitError:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"  Rate limited. Waiting {delay:.1f}s (attempt {attempt+1})")
            time.sleep(delay)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(base_delay)
    raise RuntimeError(f"Failed after {max_retries} retries")
```

## Handling Insufficient Data

| Situation | Action |
|-----------|--------|
| **Pipeline has nothing to process** | Log "no input data", write report noting empty input, exit cleanly with status "no_data" |
| **A stage produces empty output** | Log warning, pass empty collection to next stage, do NOT skip or error. Let downstream stages handle empty input gracefully |
| **External API unavailable** | Retry with backoff. After max retries, mark stage as "degraded", continue with cached/partial data if available. Log what was skipped |
| **Checkpoint file corrupted** | Delete checkpoint, re-run stage from scratch. Log the corruption event |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| No checkpointing on jobs > 5 min | Add checkpoint writes every N items and on stage completion |
| Monolithic single-function pipeline | Split into discrete stages with clear input/output contracts |
| Silently skipping failed items | Log every failure with item ID, error, timestamp |
| Hardcoded analysis depth | Use `choose_depth()` or equivalent based on actual item count |
| Retry without backoff | Always exponential backoff with jitter for external calls |
| Non-atomic checkpoint writes | Write to .tmp then rename (atomic on POSIX) |
| Ignoring partial failures | Collect errors, continue processing, summarize in report |
| No progress visibility | Log stage entry/exit, item counts, elapsed time |

## Boundaries

**SHOULD do:**
- Manage pipeline stage sequencing and dependencies
- Handle interruptions gracefully (Ctrl+C saves checkpoint)
- Scale depth to data size automatically
- Log progress with structured, parseable output
- Produce a status report at `docs/analysis/03-automated-orchestration.md`

**Should NOT do:**
- Make analytical conclusions (that is for domain-specific downstream skills)
- Silently skip failed stages without logging
- Retry indefinitely without backoff
- Decide what data means -- only move it through stages reliably

## Report Output

The pipeline MUST end by writing its status to `docs/analysis/03-automated-orchestration.md` containing:

- Pipeline run timestamp
- Table of stages: name, status (complete/failed/interrupted/skipped), item count, error count, elapsed time
- Section listing any interruptions or skipped steps with reasons
- Summary of depth tier selected and why
