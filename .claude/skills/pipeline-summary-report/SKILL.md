---
name: pipeline-summary-report
description: Use when all pipeline analysis reports are complete and a unified summary is needed, when combining findings from multiple analysis phases into a single executive overview, or when producing a final deliverable that summarizes both the composite picture and individual report findings
---

# Pipeline Summary Report

## Overview

Produce a unified summary of all completed pipeline analysis reports. The core principle: **read every report, synthesize a composite executive summary of the full persona, then summarize each report individually — the reader should understand the complete picture from the top section alone, but can drill into any specific analysis below.**

## When to Use

- All (or most) pipeline skills have completed and written reports to `docs/analysis/`
- A final deliverable is needed that combines findings across all phases
- Stakeholder needs a single document covering the entire analysis without reading 25+ separate reports
- Pipeline orchestrator signals that synthesis is complete and summary is the final step

**When NOT to use:**
- Reports are still actively being generated (wait for pipeline completion)
- Only a single report needs review (just read that report directly)
- You need to produce the subagent instruction prompt (that is skill 25, not this skill)

## Core Pattern

```
Read all reports in docs/analysis/ (01 through 25)
    |
    v
[Executive Summary] -- synthesize key findings across ALL reports into a narrative
    |
    v
[Per-Report Summaries] -- summarize each report's findings in 3-8 bullet points
    |
    v
[Pipeline Health] -- note any failed/missing/low-confidence reports
    |
    v
Write to docs/analysis/26-pipeline-summary.md
```

## Implementation

### Step 1: Inventory Available Reports

Scan `docs/analysis/` for all report files. Classify each as:
- **Present**: File exists with substantive content
- **Missing**: File does not exist (skill was not run or failed)
- **Stub**: File exists but is under 500 bytes or contains error markers

```python
from pathlib import Path

REPORT_DIR = Path("docs/analysis")
EXPECTED_REPORTS = {
    "01": "csv-metadata-forensic",
    "02": "tiered-processing-pipeline",
    "02b": "content-hydration",
    "03": "automated-orchestration",
    "04": "taxonomic-interest-classification",
    "05": "nmf-topic-modeling",
    "06": "llm-relevance-scoring",
    "07": "vader-sentiment-analysis",
    "08": "weighted-engagement-scoring",
    "09": "supplementary-engagement",
    "10": "network-social-graph",
    "11": "longitudinal-growth-curves",
    "12": "temporal-circadian-patterns",
    "13": "taxonomic-shift-detection",
    "14": "mdpi-hypernetwork-archetype",
    "15": "big-five-personality",
    "16": "liwc-psycholinguistic",
    "17": "cat-linguistic-style-matching",
    "18": "stylometric-fingerprinting",
    "19": "readability-lexical-diversity",
    "20": "rhetorical-discourse-structure",
    "21": "register-variation-code-switching",
    "22": "speech-act-pragmatic",
    "23": "archetype-assignment",
    "24": "style-specification",
    "25": "subagent-instruction",
}
```

### Step 2: Read and Synthesize

For each present report, read the full content. Then produce two outputs:

**A. Executive Summary (top of report)**
This is NOT a list of bullet points from each report stitched together. It is a **synthesized narrative** that answers:
- Who is this person, in behavioral and communicative terms?
- What is their assigned archetype and why?
- What are the 3-5 most distinctive traits of their writing voice?
- What are the key constraints for replicating their voice?
- What is the confidence level, given data quality and analysis coverage?

Write this as 2-4 paragraphs of flowing prose. The reader should understand the complete persona from this section alone.

**B. Per-Report Summaries**
For each completed report, write a section with:
- The report title and skill number
- 3-8 bullet points of key findings (quantitative where possible)
- Any caveats or low-confidence flags from the original report

Group these by pipeline phase:
1. Data Preparation (reports 01-03 + 02b)
2. Content and Interest Analysis (reports 04-06)
3. Sentiment and Engagement (reports 07-10)
4. Temporal and Behavioral (reports 11-13)
5. Psycholinguistic Profiling (reports 14-22)
6. Classification and Synthesis (reports 23-25)

### Step 3: Pipeline Health Section

At the end of the report, include:
- Table of all expected reports with status (present / missing / stub)
- Count of completed vs. total skills
- Any reports that flagged low-confidence or insufficient data
- Whether the final subagent instruction (skill 25) was produced

## Report Template

Write to `docs/analysis/26-pipeline-summary.md`:

```markdown
# Pipeline Summary Report

Generated: [timestamp]
Reports analyzed: [N] of [total expected]
Pipeline status: [COMPLETE / PARTIAL]

---

## Executive Summary

[2-4 paragraphs synthesizing the complete persona picture. Who is this person?
What defines their voice? What are the key constraints for replication?
What is the confidence level?]

---

## Phase 1: Data Preparation

### 01 — CSV Metadata Forensic Reconstruction
- [key finding]
- [key finding]
- ...

### 02 — Tiered Processing Pipeline
- [key finding]
- ...

### 02b — Content Hydration
- [key finding]
- ...

### 03 — Automated Orchestration
- [key finding]
- ...

## Phase 2: Content and Interest Analysis

### 04 — Taxonomic Interest Classification
- [key finding]
- ...

[... continue for all phases and reports ...]

---

## Pipeline Health

| # | Report | Status | Confidence |
|---|--------|--------|------------|
| 01 | CSV Metadata Forensic | COMPLETE | high |
| 02 | Tiered Processing | COMPLETE | high |
| ... | ... | ... | ... |

### Missing Reports
- [list any missing reports and their impact on the overall analysis]

### Low-Confidence Flags
- [list any reports that flagged data quality issues or low confidence]

### Final Deliverables
- Archetype assignment: [present/missing] — docs/analysis/23-archetype-assignment.md
- Style specification: [present/missing] — docs/analysis/24-style-specification.md
- Subagent instruction: [present/missing] — docs/analysis/25-subagent-instruction.md
```

## Good Patterns

- **Synthesize, don't concatenate**: The executive summary should tell a story, not repeat bullet points. Connect findings across reports — e.g., "The high Openness score (Big Five) aligns with the polymathic interest classification, and both are reflected in the user's register variation across 14 distinct subreddit communities."
- **Quantify everything**: Prefer "TTR of 0.72 indicating high lexical diversity" over "diverse vocabulary."
- **Flag uncertainty explicitly**: If a report noted low confidence or insufficient data, carry that caveat into the summary. Do not present low-confidence findings as definitive.
- **Respect the archetype**: The archetype assignment (skill 23) is the organizing frame. Lead with it in the executive summary and show how other findings support or nuance it.
- **Include the subagent prompt status**: The pipeline's ultimate deliverable is the subagent instruction. State clearly whether it was produced and at what confidence level.

## Anti-Patterns

| Mistake | Why It Fails | Fix |
|---------|-------------|-----|
| Listing bullet points from each report without synthesis | Reader still has to do the mental work of connecting findings | Write flowing prose in the executive summary that draws connections |
| Omitting missing reports from the summary | Reader doesn't know what's missing and may assume completeness | Always include the Pipeline Health table showing all expected reports |
| Parroting numbers without interpretation | "Flesch-Kincaid 12.3" means nothing without context | Always translate metrics to plain language: "writes at a 12th-grade level" |
| Presenting low-confidence findings as definitive | Misleads about analysis reliability | Prefix with confidence level or caveat |
| Writing the summary before reading ALL available reports | Early reports bias the synthesis | Read all reports first, take notes, then write the summary |

## Boundaries

**This skill SHOULD:**
- Read all available reports in `docs/analysis/`
- Produce a synthesized executive summary narrative
- Summarize each report individually with quantitative findings
- Report pipeline health and missing/failed analyses
- Write to `docs/analysis/26-pipeline-summary.md`

**This skill should NOT:**
- Re-run any analysis or produce new analytical findings
- Modify upstream reports
- Substitute its own judgment for the archetype assignment
- Produce the subagent instruction prompt (that is skill 25)
- Claim completeness when reports are missing

## Insufficient Data Handling

| Condition | Action |
|-----------|--------|
| **Fewer than 10 reports present** | Write summary of available reports; flag as "preliminary — insufficient coverage for full synthesis" |
| **No archetype assignment (report 23)** | Note absence in executive summary; present available findings without archetype framing |
| **No synthesis reports (23-25)** | Summarize phases 1-5 findings only; note "synthesis phase not completed" |
| **Reports present but mostly stubs/failures** | List what exists; write executive summary as "limited analysis" with explicit gaps |
| **All reports present and complete** | Full summary with high-confidence executive synthesis |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Writing the executive summary first, then the per-report sections | Read all reports first, write per-report summaries, THEN synthesize the executive summary from your notes |
| Making the summary longer than the sum of its parts | Each per-report section should be 3-8 bullets. The executive summary should be 2-4 paragraphs. Total should be concise. |
| Not linking back to source reports | Include the report path (e.g., `docs/analysis/15-big-five-personality.md`) so readers can drill into detail |
| Ignoring cross-report contradictions | If Big Five says low Openness but taxonomy says polymathic, note the tension explicitly |
