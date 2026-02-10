---
name: csv-metadata-forensic
description: Use when analyzing structured data exports containing multiple CSV files, reconstructing user activity timelines from metadata headers, calculating account lifespan or content creation baselines, or cross-referencing schemas across export files to identify data gaps and quality issues
---

# CSV Metadata Forensic Reconstruction

## Overview

Reconstruct a user's activity history by cross-referencing metadata headers across multiple CSV export files. The core principle: **headers are the schema, timestamps are the skeleton, and cross-file key relationships are the connective tissue** -- before analyzing content, extract everything the metadata alone can tell you.

## When to Use

- Multiple CSV files from a structured data export (platform takeout, GDPR export, API dump)
- Need to establish baseline metrics before deeper content analysis
- Need to identify data gaps, missing files, or schema inconsistencies
- Calculating account lifespan, activity frequency, content creation ratios
- Building a timeline of user activity from timestamps scattered across files

**When NOT to use:**
- Single CSV file with no cross-reference potential
- Unstructured data (logs, freeform text) -- use log parsing techniques instead
- When you need content-level analysis (sentiment, topic modeling) -- this skill is metadata-only

## Core Pattern

```
1. INVENTORY  -->  2. SCHEMA MAP  -->  3. CROSS-REFERENCE  -->  4. TEMPORAL  -->  5. METRICS  -->  6. REPORT
  List files       Extract headers     Find shared keys        Build timeline    Calculate       Write findings
  + checksums      + detect types      + validate joins        + find bounds     baselines       + flag gaps
```

## Quick Reference

| Step | Action | Tool | Key Output |
|------|--------|------|------------|
| Inventory | List all CSVs, row counts, checksums | `wc -l`, `sha256sum`, `ls -la` | File manifest with sizes |
| Schema Map | Extract header row from each file | `head -1 *.csv` | Header-per-file table |
| Type Detection | Infer column types from sample rows | `pandas.dtypes`, manual inspection | Type map per column |
| Key Discovery | Find shared column names across files | Set intersection on headers | Join key candidates |
| Temporal Bounds | Find min/max timestamps per file | `pandas.min()/.max()` on date cols | Activity window per file |
| Baseline Metrics | Calculate ratios and frequencies | Arithmetic on row counts + time | Lifespan, ratios, rates |
| PII Scan | Flag columns containing personal data | Pattern match (email, IP, phone) | PII inventory |
| Gap Analysis | Identify missing data and schema holes | Cross-reference expectations vs. reality | Data quality report |

## Implementation

### Step 1: File Inventory

List every CSV. Record filename, size, row count, and checksum (if a checkfile exists).

```python
import os, csv
from pathlib import Path

export_dir = Path(".")
manifest = {}
for f in sorted(export_dir.glob("*.csv")):
    with open(f) as fh:
        reader = csv.reader(fh)
        headers = next(reader, [])
        row_count = sum(1 for _ in reader)  # excludes header
    manifest[f.name] = {
        "size_bytes": f.stat().st_size,
        "row_count": row_count,
        "headers": headers,
    }
```

**Validate against checkfile:** If the export includes a checksum manifest (e.g., `checkfile.csv` with `filename,sha256`), verify every file's hash matches. Flag mismatches as potential corruption or tampering.

### Step 2: Schema Mapping

Build a unified schema map: which columns appear in which files, and which columns are shared across files.

```python
from collections import defaultdict

col_to_files = defaultdict(list)
for fname, info in manifest.items():
    for col in info["headers"]:
        col_to_files[col].append(fname)

# Shared keys = columns appearing in 2+ files
shared_keys = {col: files for col, files in col_to_files.items() if len(files) > 1}
```

**Key shared columns to look for:**
- `id` -- content identifiers (may need disambiguation: post ID vs. comment ID)
- `permalink` -- URL-based content locators
- `date` / `timestamp` / `created_at` -- temporal anchors
- `subreddit` / `channel` / `category` -- grouping dimensions
- `ip` -- network location (flag as PII)

### Step 3: Temporal Skeleton

Extract the earliest and latest timestamp from every file that has a date column. This establishes the **activity window** per data type.

```python
import pandas as pd

temporal_bounds = {}
for fname, info in manifest.items():
    date_cols = [c for c in info["headers"] if c in ("date", "created_at", "sent_at", "timestamp")]
    if not date_cols:
        continue
    df = pd.read_csv(fname, usecols=date_cols, parse_dates=date_cols)
    for col in date_cols:
        series = df[col].dropna()
        if series.empty:
            continue
        temporal_bounds[f"{fname}.{col}"] = {
            "earliest": series.min(),
            "latest": series.max(),
            "count": len(series),
        }
```

**Account lifespan** = delta between the registration timestamp (often in a `statistics` or `account` file) and the most recent activity timestamp across all files.

### Step 4: Baseline Metrics

Calculate these from metadata alone -- no content parsing required:

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Account lifespan** | `max(all timestamps) - registration_date` | Total active period |
| **Content creation ratio** | `post_count / comment_count` | Creator vs. participant |
| **Activity rate** | `total_items / lifespan_days` | Average daily output |
| **Active day ratio** | `unique_active_days / lifespan_days` | Consistency of engagement |
| **Subreddit/channel concentration** | `top_3_groups / total_items` | Specialist vs. generalist |
| **Temporal coverage** | `files_with_timestamps / total_files` | Data completeness |
| **Header-to-data files** | Compare `_headers` files to full data files | Schema documentation completeness |

### Step 5: PII Scan

Before proceeding to any downstream analysis, flag columns that contain personally identifiable information:

| Pattern | Columns to Flag | Action |
|---------|-----------------|--------|
| IP addresses | `ip`, network logs | Flag, do not include in reports without explicit consent |
| Email addresses | `email`, `email_address` | Flag, redact in outputs |
| Phone numbers | `phone_number`, `linked_phone` | Flag, redact in outputs |
| Birthdates | `birthdate` | Flag, note age-related sensitivity |
| Usernames linked to real identity | `linked_identities` | Flag, assess cross-platform exposure |

**Rule:** Always flag PII. Never silently pass it through to reports.

### Step 6: Gap Analysis

Identify what is missing or inconsistent:

- **Empty files**: Row count = 0 but file exists (feature never used, or data was purged)
- **Missing timestamps**: Files without date columns cannot be placed on the timeline
- **IP gaps**: Some records have IPs, others do not (platform may only log recent activity)
- **Schema mismatches**: `_headers` file columns do not match the full data file columns
- **Orphan references**: `parent` IDs in comments that do not map to any known `id`

### Step 7: Write Report

Output findings to `docs/analysis/01-csv-metadata-forensic.md`. The report structure:

```markdown
# CSV Metadata Forensic Reconstruction Report

## File Inventory
[Table: filename, row count, size, has timestamps, has PII]

## Schema Map
[Table: column name, which files contain it, inferred type]

## Temporal Skeleton
[Table: file, earliest timestamp, latest timestamp, record count]
[Account lifespan calculation]

## Baseline Metrics
[All calculated metrics with values]

## PII Inventory
[Table: column, file, data type, recommended handling]

## Data Quality Issues
[List of gaps, mismatches, empty files, orphan references]

## Recommendations for Downstream Analysis
[What analyses are viable given the data quality]
[What analyses are NOT viable due to insufficient data]
```

## Good Patterns

- **Checksum-first**: Validate file integrity before any analysis. Corrupted files produce misleading metrics.
- **Headers before content**: Read only row 1 of each file during schema mapping. Do not load full datasets until you know what you are working with.
- **Explicit type inference**: Do not trust `pandas.read_csv` auto-detection for dates. Pass `parse_dates=` explicitly for known date columns. Verify with `.dtypes`.
- **Quarantine bad rows**: When a row fails to parse, log it with filename + line number instead of silently dropping it.
- **Schema reconciliation via `pd.concat`**: When merging data from files with slightly different schemas, use `pd.concat` with `join="outer"` and track which columns came from which files.
- **Least-frequency-of-occurrence**: Rare values in metadata columns (unusual subreddits, one-off IPs) are often the most analytically interesting.

## Anti-Patterns

| Mistake | Why It Fails | Fix |
|---------|-------------|-----|
| Jumping to content analysis before schema mapping | You miss structural issues (wrong joins, missing columns) that corrupt all downstream results | Always complete Steps 1-3 before touching content |
| Assuming all `id` columns refer to the same entity | Post IDs and comment IDs are different namespaces | Disambiguate by file origin: `posts.id` vs `comments.id` |
| Treating empty IP fields as "no data" | Platforms often only log IPs for recent activity; absence is informative | Note the IP coverage window explicitly |
| Using `pd.read_csv` without specifying `dtype` | Auto-detection converts IDs to integers, losing leading zeros or causing overflow | Use `dtype=str` for ID and hash columns |
| Calculating activity rate using calendar days | Account may have been dormant for years, inflating the denominator | Report both calendar-day rate and active-day rate |
| Ignoring `_headers` files | These are the platform's declared schema -- comparing them to actual data files reveals undocumented columns or schema drift | Always diff `_headers` vs full data file headers |
| Drawing behavioral conclusions from metadata alone | Metadata tells you WHAT and WHEN, not WHY | State observations, not inferences about motivation |

## Boundaries

**This skill SHOULD:**
- Parse metadata headers and calculate structural baselines
- Identify join keys and cross-file relationships
- Calculate temporal bounds and activity metrics
- Flag PII for downstream handling
- Identify data gaps and quality issues
- Produce a structured report of findings

**This skill should NOT:**
- Make behavioral inferences beyond what metadata supports (e.g., "user was depressed during gap" from an activity hiatus)
- Perform content analysis (sentiment, topic modeling, psycholinguistics)
- Handle PII without flagging it -- every PII column must be inventoried
- Skip data validation -- never assume files are complete or uncorrupted
- Combine data from different users or accounts without explicit disambiguation

## Insufficient Data Handling

### Minimum Viable Data

To produce any meaningful output, you need **at minimum**:
- 2+ CSV files with at least 1 shared column (for cross-referencing)
- At least 1 file with a timestamp column (for temporal analysis)
- At least 1 file with > 0 data rows (for baseline metrics)

### What to Do When Data Is Missing

| Condition | Impact | Action |
|-----------|--------|--------|
| **No checkfile** | Cannot verify integrity | Note "integrity unverified" in report; proceed with caution |
| **No timestamp columns** | Cannot build timeline | Report only structural metrics (row counts, schema map); skip temporal analysis |
| **Single CSV file** | No cross-referencing possible | Report schema and row-level stats only; note "insufficient corpus for forensic reconstruction" |
| **Empty files (0 rows)** | Feature unused or data purged | List as "present but empty" in inventory; do not exclude from schema map |
| **Truncated timestamps** | Date-only (no time) reduces temporal resolution | Note precision level; proceed with date-granularity analysis |
| **Corpus < 10 records total** | Metrics are not statistically meaningful | Calculate but flag all metrics as "low-confidence" with the sample size |
| **Missing registration date** | Cannot calculate account lifespan | Use earliest observed timestamp as proxy; note it is a lower bound |
| **Schema mismatch between header and data files** | Declared schema does not match reality | Report both schemas; use actual data file headers for analysis |

**When in doubt, report what you CAN determine and explicitly state what you CANNOT.** An incomplete report that flags its own gaps is more valuable than a complete-looking report built on silent assumptions.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Reporting metrics without noting sample size | Always include `n=` with every metric |
| Conflating "no data" with "no activity" | Absence of data may mean the platform did not export it, not that the user did not do it |
| Treating all CSVs as independent | Check for parent-child relationships (comments referencing posts via `parent` or `link` columns) |
| Ignoring file metadata (modification dates, sizes) | OS-level file metadata can reveal export timing even when file contents lack timestamps |
| Not checking for duplicate rows | Exports sometimes contain duplicates; deduplicate on `id` + `date` before counting |

## References

- [Forensic Focus: CSV File Meta Data](https://www.forensicfocus.com/forums/general/csv-file-meta-data/)
- [Mastering Forensic Timelines: Tools and Techniques for DFIR](https://www.gopher.security/news/mastering-forensic-timelines-tools-and-techniques-for-dfir)
- [Timeline-Based Event Reconstruction for Digital Forensics (SoK)](https://arxiv.org/html/2504.18131v1)
- [csvkit Documentation](https://csvkit.readthedocs.io/)
- [CSV Formatting Tips for Data Accuracy (Integrate.io)](https://www.integrate.io/blog/csv-formatting-tips-and-tricks-for-data-accuracy/)
- [SANS: Timeline Analysis with Apache Spark and Python](https://www.sans.org/blog/timeline-analysis-with-apache-spark-and-python/)
- [Forensic Data Validation (Vaia)](https://www.vaia.com/en-us/explanations/law/forensic-science/forensic-data-validation/)
