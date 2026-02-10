# Written Voice Replication

A Claude Code pipeline that analyzes text corpora and produces voice-replication prompts. The pipeline runs 25 analytical skills across 4 phases (Data Prep, Analysis, Profiling, Synthesis) coordinated by 6 agents.

## Directory Conventions

- `docs/analysis/` — Generated analysis reports (one per skill, numbered 01-26)
- `docs/analysis_methods.md` — Master methodology guide for all 25 skills
- `data/enriched/` — Hydrated/enriched data produced during content hydration
- `.claude/agents/` — Agent definitions (pipeline-orchestrator, data-prep, analysis-agent, profiling-agent, synthesis-agent, plus example voice agent)
- `.claude/skills/` — Skill definitions (one directory per skill with SKILL.md)
- `scripts/` — Helper scripts (e.g., Reddit content hydration)

## Pipeline Execution

Use the `pipeline-orchestrator` agent to run the full analysis. It coordinates Data Prep, Analysis, Profiling, and Synthesis phases in the correct order with resume support.

## Data Expectations

The pipeline operates on structured CSV exports containing text content and timestamps. Place your data export files in the project root directory. The data-prep agent will inventory, validate, and process them.

Reddit GDPR exports are the primary documented data source, with a hydration script at `scripts/hydrate.py`. Other structured CSV exports with text + timestamp columns are supported via the generic skill definitions.

## Example Output

The `aaddrick-voice` agent (`.claude/agents/aaddrick-voice.md`) and `aaddrick-voice-replication` skill (`.claude/skills/aaddrick-voice-replication/`) are included as working examples of completed pipeline output. Your pipeline run will produce similar files customized to your corpus.
