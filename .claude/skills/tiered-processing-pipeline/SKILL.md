---
name: tiered-processing-pipeline
description: Use when processing raw data exports through staged pipelines, cleaning text corpora with CLI tools before deeper Python analysis, building multi-stage ETL for CSV/JSON data, or integrating LLM analysis with traditional NLP pipelines
---

# Tiered Computational Processing Pipeline

## Overview

A staged methodology for processing raw data exports: CLI tools handle initial cleaning and validation, then Python frameworks perform deeper analysis. Each stage has explicit inputs, outputs, and validation gates. Raw data is never modified in place.

## When to Use

- Processing a raw data export (CSV, JSON, or mixed) into structured analytical datasets
- Building a repeatable pipeline from messy source files to clean, enriched corpora
- Combining CLI tools (csvkit, jq, minet, exiftool) with Python analysis (pandas, spaCy, NLTK)
- Integrating LLM-based scoring or classification into a traditional analysis pipeline
- Need checkpoint/resume capability across long-running analytical workflows

**When NOT to use:**
- Single-file, single-pass transformations (just use pandas directly)
- Real-time streaming data (this is batch-oriented)
- When the data is already clean and structured for immediate analysis

## Core Pattern

```
RAW DATA (immutable)
    |
    v
[Stage 1: CLI Triage] --- validate --> checkpoint
    |
    v
[Stage 2: Python Enrichment] --- validate --> checkpoint
    |
    v
[Stage 3: Analytical Integration] --- validate --> checkpoint
    |
    v
ANALYSIS-READY DATASET + pipeline report
```

**Iron rule:** Every stage reads from the previous stage's output directory and writes to its own. Raw data is NEVER modified. If a stage fails, you can re-run it without re-running earlier stages.

## Stage Reference

### Stage 1: CLI Triage (cleaning, parsing, extraction)

**Purpose:** Validate structure, clean encoding, extract metadata, normalize formats.

| Tool | Use For | Example |
|------|---------|---------|
| `csvkit` | CSV validation, column selection, format conversion | `csvclean data.csv`, `csvcut -c 1,3,5 data.csv` |
| `jq` | JSON filtering, transformation, flattening | `jq '.[] | {id, text, date}' export.json` |
| `minet` | URL parsing, web content extraction, social media data | `minet url-parse url_column file.csv` |
| `exiftool` | File metadata extraction (images, documents) | `exiftool -csv -r media_dir/` |
| `qsv` | High-performance CSV operations (large files) | `qsv stats data.csv`, `qsv dedup data.csv` |
| `iconv`/`uchardet` | Encoding detection and conversion | `uchardet file.csv`, `iconv -f LATIN1 -t UTF-8` |

**Stage 1 checklist:**
1. Detect and fix encoding issues (`uchardet` then `iconv` if needed)
2. Validate CSV/JSON structure (`csvclean --dry-run` or `jq empty`)
3. Remove exact duplicates (`qsv dedup` or `csvkit` pipeline)
4. Extract and normalize timestamps to ISO 8601
5. Parse and catalog any embedded URLs (`minet url-parse`)
6. Write cleaned output to `stage1_output/` directory
7. Generate `stage1_manifest.json` with row counts, column names, encoding, and any rows quarantined

**Validation gate:** Compare input row count vs. output row count + quarantined rows. They MUST sum to the original. If they do not, the stage has silently dropped data -- stop and investigate.

### Stage 2: Python Enrichment (NLP, structuring, scoring)

**Purpose:** Tokenize, tag, extract entities, compute features, score content.

| Tool | Use For | Example |
|------|---------|---------|
| `pandas` | Dataframe operations, joins, aggregations | `pd.read_csv('stage1_output/clean.csv')` |
| `spaCy` | Tokenization, NER, POS tagging, dependency parsing | `nlp.pipe(texts, batch_size=50)` |
| `NLTK` | Sentiment (VADER), specialized tokenizers, lexical analysis | `SentimentIntensityAnalyzer().polarity_scores(text)` |
| `scikit-learn` | TF-IDF, NMF topic modeling, clustering | `NMF(n_components=10).fit(tfidf_matrix)` |
| `dateutil` | Robust date parsing across formats | `parser.parse(date_string)` |

**Stage 2 checklist:**
1. Load Stage 1 outputs, verify manifest checksums
2. Run spaCy pipeline for NER, POS, dependency parse (use `nlp.pipe` for batch efficiency)
3. Compute VADER sentiment scores at desired granularity (title, body, combined)
4. Extract and categorize entities (persons, organizations, locations, URLs)
5. Build TF-IDF matrix and run topic model if corpus is large enough (see Insufficient Data section)
6. Write enriched output to `stage2_output/` with one row per original record
7. Generate `stage2_manifest.json` with feature coverage stats (what percentage of records got NER, sentiment, etc.)

**Validation gate:** Every record from Stage 1 must appear in Stage 2 output. No records silently dropped. Feature coverage should be reported even if some features are null (sparse metadata is fine; silently missing records are not).

### Stage 3: Analytical Integration (LLM scoring, synthesis)

**Purpose:** Apply LLM-based analysis, cross-reference enriched features, prepare final dataset.

| Tool | Use For | Example |
|------|---------|---------|
| LLM API (Ollama, API) | Relevance scoring, summarization, classification | Batch process with rate limiting |
| `pandas` | Final joins, aggregations, pivot tables | Merge Stage 2 outputs into unified frame |
| Custom scorers | Weighted engagement, authority metrics | Composite scoring functions |

**Stage 3 checklist:**
1. Load Stage 2 outputs, verify manifest
2. Apply LLM-based scoring in batches with rate limiting and retry logic
3. Compute composite metrics (engagement scores, authority indices)
4. Cross-reference features (e.g., high-sentiment + high-engagement = authority peak)
5. Write final dataset to `stage3_output/`
6. Generate `stage3_manifest.json` and pipeline summary report

**Validation gate:** Final record count must match Stage 2. LLM scoring coverage should be reported (some records may fail LLM scoring -- quarantine, do not drop).

## Good Patterns

- **Immutable raw data:** Copy, never modify. Every stage reads from its predecessor's output directory.
- **Manifest files at every gate:** JSON files recording row counts, column schemas, checksums, quarantine counts. These are your audit trail.
- **Quarantine over discard:** Records that fail validation go to a quarantine file, never silently dropped. The quarantine file is part of the manifest.
- **Batch processing with spaCy:** Always use `nlp.pipe(texts, batch_size=50)` instead of processing one document at a time. 10-50x faster.
- **Defensive timestamp parsing:** Never assume a single date format. Use `dateutil.parser.parse` with fallback chains.
- **Rate-limited LLM calls:** When integrating LLMs in Stage 3, implement exponential backoff and checkpoint after each batch so interrupted runs can resume.
- **Pipeline idempotency:** Re-running any stage with the same inputs should produce the same outputs. No append-only side effects.

## Anti-Patterns

| Mistake | Why It Fails | Fix |
|---------|-------------|-----|
| Modifying raw data in place | Cannot re-run pipeline; original state lost forever | Always write to separate output directory |
| Skipping validation between stages | Silent data loss compounds through pipeline; final results are wrong but look plausible | Implement row-count reconciliation at every gate |
| Over-processing in Stage 1 | CLI tools are for structural cleaning, not analysis; NLP in bash is fragile | Keep Stage 1 to encoding, dedup, format normalization; defer NLP to Stage 2 |
| Processing records one-at-a-time in spaCy | Orders of magnitude slower than batch | Use `nlp.pipe()` with appropriate batch size |
| Assuming data format without inspection | CSV might have mixed delimiters, JSON might be JSONL, encoding might vary | Always run format detection before processing |
| Discarding records that fail a stage | Survivorship bias corrupts all downstream analysis | Quarantine failed records; report coverage rates |
| Running LLM scoring without checkpoints | API failures at record 4,999 of 5,000 lose all work | Checkpoint every N records; implement resume logic |
| Performing final analysis in the cleaning stage | Conflates data preparation with interpretation; makes pipeline non-reusable | Cleaning stages produce clean data, not conclusions |

## Insufficient Data Handling

| Condition | Detection | Graceful Degradation |
|-----------|-----------|---------------------|
| Very small corpus (<50 records) | Row count in Stage 1 manifest | Skip topic modeling (NMF needs statistical mass); focus on per-record NLP features instead |
| Sparse metadata (>50% null in a column) | Feature coverage in Stage 2 manifest | Report the column as sparse; do not impute values without explicit user consent; exclude from aggregate metrics |
| Unexpected format (not CSV/JSON) | Format detection failure in Stage 1 | Halt pipeline with diagnostic message; do not guess -- ask user to confirm format |
| Mixed encodings within a file | `uchardet` returns low confidence | Process line-by-line with per-line encoding detection; quarantine lines that fail |
| No text content (metadata-only export) | All text columns empty or absent | Skip NLP stages entirely; pivot to metadata-only analysis (timestamps, categories, network structure) |
| LLM API unavailable | Connection/auth failure in Stage 3 | Complete pipeline through Stage 2; flag Stage 3 as incomplete; produce partial report |

**Principle:** When data is insufficient for a technique, report what you cannot do and why, then proceed with what you can. Never silently skip an analysis step or fabricate data to fill gaps.

## Pipeline Report Output

The final step of any pipeline run MUST produce a report at `docs/analysis/02-tiered-processing-pipeline.md` containing:

```markdown
# Tiered Processing Pipeline Report

## Pipeline Configuration
- Source files processed: [list]
- Stages executed: [1, 2, 3] or subset
- Tools used per stage: [list]
- Timestamp: [ISO 8601]

## Stage Results

### Stage 1: CLI Triage
- Input records: [N]
- Output records: [N]
- Quarantined records: [N] (reasons: ...)
- Encoding issues detected: [yes/no, details]
- Duplicate records removed: [N]

### Stage 2: Python Enrichment
- Records processed: [N]
- NER coverage: [X%]
- Sentiment coverage: [X%]
- Topic model: [fitted / skipped due to small corpus]
- Features generated: [list]

### Stage 3: Analytical Integration
- Records scored by LLM: [N of M]
- Composite metrics computed: [list]
- Cross-reference findings: [summary]

## Data Quality Observations
- [List any anomalies, sparse columns, format issues]
- [Coverage gaps and their impact on downstream analysis]

## Recommendations
- [What additional data or processing would improve results]
```

## Common Mistakes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Final dataset has fewer rows than raw export | Silent drops between stages | Check manifests; reconcile row counts at every gate |
| Sentiment scores are all neutral | Text was not decoded properly; HTML entities or markup in text | Add HTML stripping / entity decoding to Stage 1 |
| Topic model produces incoherent topics | Corpus too small or stop words not removed | Check corpus size (need 100+ docs minimum); verify preprocessing |
| LLM scores are inconsistent across runs | Non-deterministic model or prompt drift | Pin model version; set temperature=0; log exact prompts |
| Pipeline takes hours on moderate data | Processing records one-at-a-time | Batch with `nlp.pipe()`; use `qsv` instead of `csvkit` for large files |
