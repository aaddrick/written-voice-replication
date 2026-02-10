# Written Voice Replication

A Claude Code project that analyzes a corpus of someone's writing and generates an AI agent that can write in that person's style.

**Use this if you want to:**
- Train an AI to write like you do (for content generation, drafting, or assistive writing)
- Replicate an author's voice for stylistic consistency across a project
- Analyze writing patterns across large text corpora
- Document and preserve a specific writing style with measurable precision

You interact with it by talking to Claude Code — an AI coding assistant that reads task definitions (called "agents" and "skills") and executes them on your behalf. You don't write any code. You just tell Claude what you want, and it orchestrates the pipeline.

## What It Produces

The pipeline analyzes your writing corpus across 25 dimensions — readability, sentence structure, sentiment, personality markers, rhetorical patterns, speech acts, and more — then synthesizes everything into:

- A **voice agent** — a Claude Code agent that writes in the analyzed style
- A **voice skill** — a detailed instruction set with writing rules, few-shot examples, and numeric targets
- A **numeric profile** — measurable validation targets (Flesch-Kincaid grade, sentence length, function-word rates, etc.)
- **26 analysis reports** — documentation of every finding along the way

The difference between agent and skill: An **agent** is a persona Claude adopts ("write as this person"). A **skill** is a capability Claude executes ("follow these rules to replicate this voice"). The pipeline produces both so you can use whichever fits your workflow.

## Try It First

The project includes a working example: a voice agent and skill generated from a real Reddit writing corpus.

Before running the pipeline on your own data, you can test the example output:

**To use the voice agent:**
```
Use the aaddrick-voice agent to write a technical tutorial
explaining how to set up SSH keys
```

**To use the voice skill:**
```
Use the aaddrick-voice-replication skill to write a product review
for a standing desk
```

The example files are at `.claude/agents/aaddrick-voice.md` and `.claude/skills/aaddrick-voice-replication/`. Read them to see what the pipeline produces from a Reddit data export. The 26 analysis reports that fed into those outputs are in `docs/analysis/`.

## Requirements

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) — an AI coding assistant that orchestrates the pipeline by reading agent and skill definitions and executing them interactively
- Python 3.8+ and `requests` (only needed if using the Reddit content hydration script)

Everything runs through Claude Code. There are no external NLP libraries or dependencies. The analysis skills use Claude's language understanding directly.

## Quick Start

1. Clone the repository and open it in Claude Code
2. Place your writing samples in the project root (see [Bringing Your Data](#bringing-your-data) below)
3. Tell Claude to run the pipeline:

```
Use the pipeline-orchestrator agent to run the full analysis
```

Claude handles the rest. It sequences 4 phases, resumes from interruptions if needed, and adapts to whatever data you provide.

## Using the Output

After the pipeline completes, you'll have:

1. A voice agent at `.claude/agents/[name]-voice.md`
2. A voice skill at `.claude/skills/[name]-voice-replication/`
3. 26 analysis reports at `docs/analysis/`

**To use the voice agent:**
```
Use the [name]-voice agent to write [whatever you need]
```

**To use the voice skill:**
```
Use the [name]-voice-replication skill to write [whatever you need]
```

You can also copy the voice agent or skill files to other projects. The agent file is self-contained markdown. The skill directory includes an instructions file and supporting documentation.

## Bringing Your Data

The pipeline needs a corpus of text written by the person whose voice you want to replicate. The more text, the better the results — but it works with as few as 50 items.

**The included data-prep phase was built around structured CSV exports** (the reference implementation uses a Reddit GDPR export). But the analysis skills themselves are format-agnostic. They operate on text, timestamps, and whatever metadata you can provide.

If your data isn't in CSV format, or comes from a different source, tell Claude what you have and ask it to help you adapt the data-prep phase. For example:

```
I have a folder of markdown blog posts instead of CSV exports.
Help me adapt the data-prep agent to inventory and process these files
so the analysis skills can run on them.
```

```
I exported my Slack messages as JSON. How should I structure this
for the pipeline?
```

```
I just have a single text file with all my writing samples.
Can we skip the CSV processing and go straight to analysis?
```

Claude can read the existing agent and skill definitions and help you modify the data-prep phase to fit your situation. Skills 4-26 don't care where the text came from — they just need cleaned text with whatever metadata is available.

### What the pipeline looks for

The more of these you can provide, the richer the analysis:

| Data | Used For | Required? |
|------|----------|-----------|
| Text content (posts, comments, messages) | All 25 analysis skills | Yes |
| Timestamps | Temporal patterns, growth curves, circadian analysis | Recommended |
| Community/context labels (subreddits, channels, tags) | Register variation, taxonomic classification, accommodation | Helpful |
| Engagement metrics (scores, votes, reactions) | Engagement scoring, sentiment-engagement correlation | Optional |
| Reply chains / parent references | Network analysis, conversation threading | Optional |

If some metadata isn't available, the pipeline degrades gracefully. It skips the skills that need it and documents what was skipped and why.

## Troubleshooting

**Pipeline fails during data prep:**
Check that your CSV has text content in a column called `body` or `text`. If your column names are different, tell Claude what they're called and ask it to update the data-prep agent.

**Missing timestamps or metadata:**
The pipeline adapts. If you don't have timestamps, it skips temporal analysis. If you don't have community labels, it skips register variation analysis. Check `docs/analysis/` after the run to see what was skipped.

**Pipeline stops mid-run:**
Tell Claude to resume. The orchestrator tracks which skills have completed and picks up where it left off.

**Output seems off or doesn't match the source writing:**
Check the corpus size. If you have fewer than 50 writing samples, the analysis may not have enough data. Try providing more text or ask Claude to regenerate specific analysis skills with different parameters.

**Can't figure out how to structure your data:**
Share a few lines of your data with Claude and ask: "How should I structure this for the pipeline?" Claude can read your files and recommend modifications to the data-prep phase.

## Customizing the Pipeline

Everything in this project is a Claude Code agent or skill definition written in markdown. You can ask Claude to modify any part of it.

**Modify an analysis skill:**
```
The rhetorical-discourse-structure skill doesn't account for
code blocks in technical writing. Can you update it to handle that?
```

**Add a new analysis dimension:**
```
I want to add a skill that analyzes emoji usage patterns.
Use the existing skills as a template.
```

**Change how the final voice prompt is structured:**
```
The subagent-instruction skill produces prompts that are too long
for my use case. Can you modify it to target under 1000 tokens?
```

**Write a hydration script for a different platform:**
```
I need a content hydration script for Hacker News comments,
similar to how scripts/hydrate.py works for Reddit.
```

## Architecture

The pipeline is organized into 4 phases coordinated by a pipeline orchestrator:

| Phase | Agent | Skills | What It Does |
|-------|-------|--------|--------------|
| Data Prep | `data-prep` | 1-3 | Inventories, validates, cleans, and enriches your data |
| Analysis | `analysis-agent` | 4-13 | Content classification, sentiment, engagement, network, temporal patterns |
| Profiling | `profiling-agent` | 14-22 | Personality, psycholinguistics, stylometrics, readability, rhetoric, speech acts |
| Synthesis | `synthesis-agent` | 23-26 | Combines everything into archetype, style spec, and voice prompt |

Analysis and Profiling run in parallel after Data Prep completes. Synthesis waits for both.

Each skill writes a report to `docs/analysis/`. The methodology guide at `docs/analysis_methods.md` documents all 25 analytical methods.

## Project Structure

```
.claude/
  agents/                          # Agent definitions (the "who")
    pipeline-orchestrator.md       #   Coordinates all phases
    data-prep.md                   #   Data preparation
    analysis-agent.md              #   Content/engagement/temporal analysis
    profiling-agent.md             #   Psycholinguistic profiling
    synthesis-agent.md             #   Final persona synthesis
    aaddrick-voice.md              #   Example output: completed voice agent
  skills/                          # Skill definitions (the "how")
    csv-metadata-forensic/         #   26 analysis skills, one directory each
    tiered-processing-pipeline/
    content-hydration/
    ...
    aaddrick-voice-replication/    #   Example output: completed voice skill
docs/
  analysis_methods.md              # Master methodology guide
  analysis/                        # Generated reports land here (01-26)
scripts/
  hydrate.py                       # Reddit content hydration (reference implementation)
```

## License

MIT — see [LICENSE](LICENSE) for details.
