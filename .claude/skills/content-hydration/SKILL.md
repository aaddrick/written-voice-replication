---
name: content-hydration
description: Use when a data export contains URLs or IDs referencing external content that is not stored inline, when comments or replies are orphaned from their parent context, when voted or saved items exist only as permalinks with no content, or when downstream analysis agents need enriched records with conversational context reconstructed from linked references
---

# Content Hydration

## Overview

Fetch linked content referenced by URLs and IDs in a structured data export to reconstruct conversational context. The core principle: **exports are skeletons — IDs and URLs point to context that must be fetched, deduplicated, cached locally, and joined back to source records before downstream analysis can produce meaningful results.**

**Reference implementation:** A working script exists at `scripts/hydrate.py` that implements this skill's patterns for the current Reddit export. **If the existing script matches your data layout and requirements, run it.** If the export format differs, columns have changed, or additional tiers are needed, **write a new script** using the patterns in this skill as a guide — do not force-fit data into a script that doesn't match. The code examples below are patterns to adapt, not rigid templates.

## When to Use

- Comments reference parent posts or parent comments by URL/ID but the parent content is not in the export
- Voted or saved items exist only as permalinks with no title, body, or metadata stored locally
- Body text contains external URLs that should be cataloged (domain, type) for interest analysis
- Multiple downstream agents need the same enriched dataset — hydrate once, consume many times
- A prior pipeline stage (e.g., tiered-processing-pipeline) has cleaned the CSVs but not resolved linked references

**When NOT to use:**
- All content is already inline (no URL/ID references to resolve)
- The export is small enough to manually inspect and enrich
- You only need metadata (timestamps, IDs, counts) — use csv-metadata-forensic instead
- External content fetching is prohibited by policy or rate limits are zero

## Core Pattern

```
CLEANED CSVs (from tiered-processing-pipeline)
    |
    v
[Tier 1: Parent Context] --- checkpoint --> deduplicated URL queue
    |                                        fetch via .json trick
    |                                        join to source records
    v
[Tier 2: Voted/Saved Content] --- checkpoint --> same fetch + join
    |
    v
[Tier 3: External URL Catalog] --- no fetching --> regex extract + classify
    |
    v
data/enriched/  +  hydration_manifest.json  +  report
```

**Iron rule:** Deduplicate URLs before fetching. Many comments share the same parent post — fetch each unique URL exactly once, then join by key.

## Quick Reference

| Step | Action | Input | Output |
|------|--------|-------|--------|
| URL Queue Build | Deduplicate all target URLs per tier | Source CSVs | Unique URL list with source-record mapping |
| Checkpoint Load | Resume from last successful fetch | `checkpoints/hydration_*.json` | Set of already-fetched URLs |
| Fetch (.json) | Append `.json` to Reddit permalink, parse response | URL queue | Raw JSON responses cached to disk |
| Rate Limit | 1 req / 2s baseline, exponential backoff on 429/503 | HTTP status codes | Controlled request pacing |
| Join | Merge fetched fields back to source records by key | Cached JSON + source CSVs | Enriched CSVs |
| Catalog | Extract external URLs from body text, classify by domain | Body text column | `external_links.csv` |
| Manifest | Record fetch stats, failures, coverage per tier | All stages | `hydration_manifest.json` |

## Implementation

### The Reddit .json Trick

Append `.json` to any Reddit permalink to get structured data without API authentication:

```
https://www.reddit.com/r/askscience/comments/6s99s7/some_title/.json
```

Returns a JSON array: `[post_listing, comments_listing]`. The post is at `[0]["data"]["children"][0]["data"]`. Comments are nested under `[1]["data"]["children"]`.

**For parent comment lookup:** Given a comment's `link` column (parent post URL) and `parent` column (bare comment ID like `dlazu42`), the parent comment data is inside the comment tree of the post JSON. Fetch the post URL with `.json`, then search the comment tree for the matching ID.

```python
import requests, time, json, re
from pathlib import Path

CACHE_DIR = Path("data/hydration_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "PersonaSynthesisPipeline/1.0 (content-hydration; research)"
}
BASE_DELAY = 2.0  # seconds between requests

def fetch_reddit_json(permalink, delay=BASE_DELAY):
    """Fetch Reddit permalink as JSON. Returns parsed data or None on failure.

    Caches responses to disk by URL hash to avoid re-fetching.
    """
    # Normalize URL: strip trailing slash, append .json
    url = permalink.rstrip("/")
    if not url.endswith(".json"):
        url += ".json"

    # Check disk cache first
    cache_key = re.sub(r'[^\w]', '_', url)[-120:]  # filesystem-safe key
    cache_path = CACHE_DIR / f"{cache_key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    # Fetch with rate limiting
    time.sleep(delay)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            cache_path.write_text(json.dumps(data))
            return data
        elif resp.status_code in (429, 503):
            return "RATE_LIMITED"
        elif resp.status_code == 404:
            cache_path.write_text(json.dumps({"_status": "not_found"}))
            return None
        else:
            return None
    except requests.RequestException:
        return None


def extract_post_from_json(data):
    """Extract post title, body, score, author from Reddit .json response."""
    if not data or not isinstance(data, list) or len(data) < 1:
        return None
    try:
        post = data[0]["data"]["children"][0]["data"]
        return {
            "title": post.get("title", ""),
            "body": post.get("selftext", ""),
            "score": post.get("score", 0),
            "author": post.get("author", "[unknown]"),
            "subreddit": post.get("subreddit", ""),
        }
    except (KeyError, IndexError, TypeError):
        return None


def find_comment_in_tree(data, target_id):
    """Recursively search the comment tree for a comment by ID.

    Reddit comment IDs in the export are bare (e.g., 'dlazu42').
    In the JSON response, 'name' is 't1_dlazu42' and 'id' is 'dlazu42'.
    """
    if not data or not isinstance(data, list) or len(data) < 2:
        return None

    def _search(children):
        for child in children:
            if child.get("kind") != "t1":
                continue
            cdata = child.get("data", {})
            if cdata.get("id") == target_id:
                return {
                    "body": cdata.get("body", ""),
                    "author": cdata.get("author", "[unknown]"),
                    "score": cdata.get("score", 0),
                }
            # Recurse into replies
            replies = cdata.get("replies")
            if isinstance(replies, dict):
                result = _search(
                    replies.get("data", {}).get("children", [])
                )
                if result:
                    return result
        return None

    return _search(data[1]["data"]["children"])
```

### Checkpoint / Resume

```python
class HydrationCheckpoint:
    """Track which URLs have been fetched across interruptions."""

    def __init__(self, tier_name, checkpoint_dir="checkpoints"):
        self.path = Path(checkpoint_dir) / f"hydration_{tier_name}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self):
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {"fetched": [], "failed": [], "rate_limited": []}

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2))
        tmp.rename(self.path)  # atomic on POSIX

    def is_done(self, url):
        return url in self.state["fetched"] or url in self.state["failed"]

    def mark_done(self, url):
        if url not in self.state["fetched"]:
            self.state["fetched"].append(url)

    def mark_failed(self, url, reason=""):
        if url not in self.state["failed"]:
            self.state["failed"].append(url)

    def mark_rate_limited(self, url):
        if url not in self.state["rate_limited"]:
            self.state["rate_limited"].append(url)
```

### Rate Limiting with Exponential Backoff

```python
import random

def fetch_with_rate_limit(url, checkpoint, max_retries=4):
    """Fetch a URL with exponential backoff on rate limits.

    Returns parsed JSON data, None (permanent failure), or raises after max retries.
    """
    delay = BASE_DELAY
    for attempt in range(max_retries):
        result = fetch_reddit_json(url, delay=delay)
        if result == "RATE_LIMITED":
            delay = BASE_DELAY * (2 ** (attempt + 1)) + random.uniform(0, 1)
            checkpoint.mark_rate_limited(url)
            checkpoint.save()
            print(f"  Rate limited. Backoff {delay:.1f}s (attempt {attempt+1})")
            time.sleep(delay)
            continue
        elif result is None:
            checkpoint.mark_failed(url, reason="fetch_error_or_404")
            checkpoint.save()
            return None
        else:
            checkpoint.mark_done(url)
            if (len(checkpoint.state["fetched"]) % 25) == 0:
                checkpoint.save()  # periodic checkpoint
            return result
    # Exhausted retries
    checkpoint.mark_failed(url, reason="max_retries_exhausted")
    checkpoint.save()
    return None
```

### Tier 1: Parent Context Enrichment

```python
import pandas as pd

def hydrate_parent_context(comments_csv, output_path):
    """Enrich comments with parent post title/body and parent comment body.

    Deduplicates parent post URLs before fetching (many comments share a parent post).
    """
    df = pd.read_csv(comments_csv, dtype=str).fillna("")
    checkpoint = HydrationCheckpoint("tier1_parents")

    # --- Step 1: Deduplicate parent post URLs ---
    unique_post_urls = df["link"].dropna().unique().tolist()
    unique_post_urls = [u for u in unique_post_urls if u.strip()]
    print(f"Tier 1: {len(unique_post_urls)} unique parent post URLs "
          f"(from {len(df)} comments)")

    # --- Step 2: Fetch parent posts ---
    post_cache = {}  # url -> extracted post dict
    for i, url in enumerate(unique_post_urls):
        if checkpoint.is_done(url):
            # Load from disk cache
            cached = fetch_reddit_json(url, delay=0)  # hits disk cache
            if cached and cached != "RATE_LIMITED":
                post_cache[url] = extract_post_from_json(cached)
            continue
        print(f"  [{i+1}/{len(unique_post_urls)}] Fetching: {url[:80]}...")
        data = fetch_with_rate_limit(url, checkpoint)
        if data:
            post_cache[url] = extract_post_from_json(data)

    # --- Step 3: Resolve parent comments ---
    comment_cache = {}  # (post_url, comment_id) -> comment dict
    # Only fetch if parent ID differs from post ID (i.e., replying to a comment, not the post)
    needs_parent_comment = df[
        (df["parent"].str.len() > 0) &
        (df["parent"] != df["id"])
    ]
    for _, row in needs_parent_comment.iterrows():
        post_url = row.get("link", "")
        parent_id = row.get("parent", "")
        if not post_url or not parent_id:
            continue
        cache_key = (post_url, parent_id)
        if cache_key in comment_cache:
            continue
        # The post JSON is already cached on disk from Step 2
        data = fetch_reddit_json(post_url, delay=0)  # hits disk cache
        if data and data != "RATE_LIMITED":
            comment_data = find_comment_in_tree(data, parent_id)
            comment_cache[cache_key] = comment_data  # may be None if not in tree

    # --- Step 4: Join enriched data back to source ---
    df["parent_post_title"] = df["link"].map(
        lambda u: (post_cache.get(u) or {}).get("title", "")
    )
    df["parent_post_body"] = df["link"].map(
        lambda u: (post_cache.get(u) or {}).get("body", "")
    )
    df["parent_post_author"] = df["link"].map(
        lambda u: (post_cache.get(u) or {}).get("author", "")
    )
    df["parent_comment_body"] = df.apply(
        lambda r: (comment_cache.get((r["link"], r["parent"])) or {}).get("body", ""),
        axis=1
    )
    df["parent_comment_author"] = df.apply(
        lambda r: (comment_cache.get((r["link"], r["parent"])) or {}).get("author", ""),
        axis=1
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    checkpoint.save()
    return checkpoint.state
```

### Tier 2: Voted / Saved Content

```python
def hydrate_votes(votes_csv, output_path, content_type="post"):
    """Fetch content for voted posts or comments.

    votes_csv has columns: id, permalink, direction
    """
    df = pd.read_csv(votes_csv, dtype=str).fillna("")
    if df.empty:
        pd.DataFrame().to_csv(output_path, index=False)
        return {"fetched": [], "failed": [], "skipped": "empty_input"}

    checkpoint = HydrationCheckpoint(f"tier2_{content_type}_votes")
    unique_urls = df["permalink"].dropna().unique().tolist()
    print(f"Tier 2 ({content_type} votes): {len(unique_urls)} unique URLs")

    results = {}
    for i, url in enumerate(unique_urls):
        if checkpoint.is_done(url):
            cached = fetch_reddit_json(url, delay=0)
            if cached and cached != "RATE_LIMITED":
                results[url] = extract_post_from_json(cached)
            continue
        print(f"  [{i+1}/{len(unique_urls)}] Fetching: {url[:80]}...")
        data = fetch_with_rate_limit(url, checkpoint)
        if data:
            results[url] = extract_post_from_json(data)

    df["fetched_title"] = df["permalink"].map(
        lambda u: (results.get(u) or {}).get("title", "")
    )
    df["fetched_body"] = df["permalink"].map(
        lambda u: (results.get(u) or {}).get("body", "")
    )
    df["fetched_score"] = df["permalink"].map(
        lambda u: (results.get(u) or {}).get("score", "")
    )
    df["fetched_subreddit"] = df["permalink"].map(
        lambda u: (results.get(u) or {}).get("subreddit", "")
    )
    df["fetched_author"] = df["permalink"].map(
        lambda u: (results.get(u) or {}).get("author", "")
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    checkpoint.save()
    return checkpoint.state
```

### Tier 3: External URL Catalog

```python
from urllib.parse import urlparse

# Domain -> category mapping (extend as needed)
DOMAIN_CATEGORIES = {
    "youtube.com": "video", "youtu.be": "video", "vimeo.com": "video",
    "github.com": "code", "gitlab.com": "code", "bitbucket.org": "code",
    "stackoverflow.com": "code", "stackexchange.com": "code",
    "imgur.com": "image", "i.redd.it": "image", "i.imgur.com": "image",
    "flickr.com": "image",
    "twitter.com": "social", "x.com": "social", "mastodon.social": "social",
    "wikipedia.org": "reference", "en.wikipedia.org": "reference",
    "arxiv.org": "academic", "doi.org": "academic", "scholar.google.com": "academic",
    "docs.google.com": "document", "drive.google.com": "document",
    "maps.google.com": "map", "google.com/maps": "map", "goo.gl": "shortlink",
    "kaggle.com": "data",
}

URL_PATTERN = re.compile(
    r'https?://[^\s\)\]\>\"\'`,;]+',
    re.IGNORECASE
)

def classify_domain(url):
    """Classify a URL by its domain into a content category."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().lstrip("www.")
        # Check full domain first, then base domain
        if domain in DOMAIN_CATEGORIES:
            return DOMAIN_CATEGORIES[domain]
        # Check if any key is a substring (e.g., "google.com/maps")
        full = domain + parsed.path.lower()
        for pattern, cat in DOMAIN_CATEGORIES.items():
            if pattern in full:
                return cat
        return "other"
    except Exception:
        return "unknown"


def catalog_external_urls(posts_csv, comments_csv, output_path):
    """Extract and classify all non-Reddit URLs from post and comment bodies.

    Does NOT fetch the URLs -- just catalogs them with domain and category.
    """
    records = []

    for source_file, source_type in [(posts_csv, "post"), (comments_csv, "comment")]:
        df = pd.read_csv(source_file, dtype=str).fillna("")
        body_col = "body"
        for _, row in df.iterrows():
            text = row.get(body_col, "")
            urls = URL_PATTERN.findall(text)
            for url in urls:
                # Skip Reddit internal links
                parsed = urlparse(url)
                if "reddit.com" in parsed.netloc or "redd.it" in parsed.netloc:
                    continue
                records.append({
                    "source_type": source_type,
                    "source_id": row.get("id", ""),
                    "source_subreddit": row.get("subreddit", ""),
                    "url": url.rstrip(".,;:!?)"),  # strip trailing punctuation
                    "domain": parsed.netloc.lower().lstrip("www."),
                    "category": classify_domain(url),
                })

    out = pd.DataFrame(records)
    if not out.empty:
        out = out.drop_duplicates(subset=["url", "source_id"])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return len(out)
```

### Hydration Manifest

```python
def write_manifest(tier_states, external_count, output_dir="data/enriched"):
    """Write hydration_manifest.json summarizing all tiers."""
    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tiers": {},
        "external_urls_cataloged": external_count,
        "status": "complete",
    }
    for tier_name, state in tier_states.items():
        fetched = len(state.get("fetched", []))
        failed = len(state.get("failed", []))
        rate_limited = len(state.get("rate_limited", []))
        total = fetched + failed
        manifest["tiers"][tier_name] = {
            "total_urls": total,
            "fetched": fetched,
            "failed": failed,
            "rate_limited_retries": rate_limited,
            "coverage_pct": round(fetched / total * 100, 1) if total else 0,
        }
        if state.get("skipped"):
            manifest["tiers"][tier_name]["skipped"] = state["skipped"]
        # Mark overall status as partial if any tier has failures
        if failed > 0:
            manifest["status"] = "partial"

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    manifest_path = Path(output_dir) / "hydration_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest
```

## Good Patterns

- **Deduplicate before fetching:** Many comments share the same parent post URL. Build a unique URL set, fetch each once, join by key afterward. This can reduce Tier 1 fetches from 1,716 to a few hundred.
- **Disk-cache every response:** Write raw JSON to `data/hydration_cache/` keyed by URL. This makes re-runs free and lets you debug parsing issues against cached data.
- **Checkpoint per tier:** Each tier has its own checkpoint file. If Tier 1 completes but Tier 2 is interrupted, only Tier 2 resumes.
- **Atomic checkpoint writes:** Write to `.tmp` then `rename()`. Prevents corruption if the process is killed mid-write.
- **Respect deleted content:** Reddit returns `[deleted]` or `[removed]` in the body field. Record these as successful fetches with the deletion marker — do not retry, do not mark as failures.
- **User-Agent header:** Always set a descriptive User-Agent. Reddit blocks requests with default Python user agents.
- **Fetch parent comments from the post's comment tree:** The parent comment ID in the export is a bare ID. Rather than constructing a separate URL, search the already-fetched post JSON's comment tree for the matching ID. This avoids additional HTTP requests.

## Anti-Patterns

| Mistake | Why It Fails | Fix |
|---------|-------------|-----|
| Fetching every comment's parent post URL individually without dedup | 1,716 fetches when 400 unique URLs suffice — wastes time and risks rate limits | Build unique URL set first, fetch once per unique URL |
| No disk cache for fetched JSON | Re-runs re-fetch everything; debugging requires live requests | Cache raw JSON response to disk keyed by URL |
| Using bare `requests.get()` without timeout | Hangs indefinitely on unresponsive servers | Always pass `timeout=15` |
| Treating `[deleted]` as a fetch failure | Retries deleted content forever, never converges | Record `[deleted]` / `[removed]` as successful fetches |
| Fetching external (non-Reddit) URLs for Tier 3 | YouTube/GitHub content is irrelevant to persona voice synthesis | Catalog only — extract domain, classify type, do not fetch |
| Setting User-Agent to default Python string | Reddit returns 429 immediately for unidentified clients | Set a descriptive project-specific User-Agent |
| No backoff on 429 responses | Rapid retries escalate to IP blocks | Exponential backoff with jitter starting at 2× base delay |
| Checkpointing only on completion | Process killed at item 499 of 500 loses all progress | Checkpoint every N items (25-50) during fetch loops |
| Joining fetched data by positional index | Row order may not match between source and enriched files | Join on a stable key (`id`, `permalink`) |

## Boundaries

**This skill SHOULD:**
- Fetch Reddit content via the `.json` permalink trick with rate limiting
- Deduplicate URLs before fetching
- Join fetched content back to source records by stable keys
- Catalog external URLs by domain and type without fetching them
- Produce checkpoint files for resumable interrupted runs
- Write enriched CSVs to `data/enriched/` for multi-agent consumption
- Write a manifest recording fetch coverage and failures per tier
- Handle deleted, removed, and missing content gracefully

**This skill should NOT:**
- Use the Reddit API or require authentication (the `.json` trick is auth-free)
- Fetch external (non-Reddit) URLs beyond cataloging domain and type
- Perform any content analysis (sentiment, topic modeling, classification) — that is for downstream skills
- Modify the original export CSVs — always write to a separate output directory
- Retry deleted or removed content — record the status and move on
- Make behavioral inferences from fetched content — only enrich and store

## Insufficient Data Handling

| Condition | Detection | Action |
|-----------|-----------|--------|
| **No `link` column in comments** | Column check during Tier 1 setup | Skip Tier 1; note "no parent references" in manifest |
| **Empty votes/saved CSVs** | Row count = 0 | Skip affected Tier 2 sub-task; note "empty input" in manifest |
| **All fetches fail (site down)** | 0 successful fetches after N attempts | Abort tier with "source_unavailable" status; write partial manifest |
| **High deletion rate (>50% `[deleted]`)** | Count deleted vs. total in tier stats | Report coverage percentage; downstream agents decide if sufficient |
| **No body text for URL extraction** | Body column empty or absent | Skip Tier 3; note "no body text for URL extraction" in manifest |
| **Rate limited beyond recovery** | Backoff exceeds 60s repeatedly | Pause tier, save checkpoint, report as "rate_limited_incomplete" |
| **Malformed URLs in source data** | URL parse failure | Log and skip; increment "malformed" counter in manifest |

**Principle:** Partial hydration is better than no hydration. Write what you have, flag what you could not get, and let downstream agents decide how to handle gaps.

## Pipeline Report Output

Write the hydration report to `docs/analysis/02b-content-hydration.md`:

```markdown
# Content Hydration Report

## Configuration
- Source files: [list of CSVs processed]
- Tiers executed: [1, 2, 3] or subset
- Fetch method: Reddit .json permalink
- Rate limit: [base delay]s baseline, exponential backoff
- Timestamp: [ISO 8601]

## Tier 1: Parent Context
- Unique parent post URLs: [N]
- Successfully fetched: [N] ([X%])
- Failed (404/deleted/error): [N]
- Parent comments resolved from post trees: [N of M]
- Output: `data/enriched/comments_with_context.csv`

## Tier 2: Voted / Saved Content
### Post Votes
- URLs: [N], Fetched: [N] ([X%]), Failed: [N]
- Output: `data/enriched/voted_posts.csv`

### Comment Votes
- URLs: [N], Fetched: [N] ([X%]), Failed: [N]
- Output: `data/enriched/voted_comments.csv`

### Saved Posts
- URLs: [N], Fetched: [N] ([X%]), Failed: [N]
- Output: `data/enriched/saved_posts.csv`

## Tier 3: External URL Catalog
- Total external URLs found: [N]
- Unique URLs after dedup: [N]
- Domain distribution: [top 10 domains with counts]
- Category distribution: [video: N, code: N, image: N, ...]
- Output: `data/enriched/external_links.csv`

## Fetch Summary
| Tier | Total URLs | Fetched | Failed | Coverage |
|------|-----------|---------|--------|----------|
| 1 - Parent Context | N | N | N | X% |
| 2 - Post Votes | N | N | N | X% |
| 2 - Comment Votes | N | N | N | X% |
| 2 - Saved Posts | N | N | N | X% |
| 3 - External Catalog | N | — | — | cataloged |

## Data Quality Notes
- [Deleted content percentage and impact]
- [Rate limiting events and recovery]
- [Any malformed URLs or unexpected formats]

## Recommendations for Downstream Analysis
- [Which enriched files are ready for consumption]
- [Coverage gaps that may affect specific analyses]
- [Whether re-running with different rate limits would improve coverage]
```

## Output Directory Structure

```
data/
  enriched/
    comments_with_context.csv   # Original comment columns + parent_post_title,
                                # parent_post_body, parent_post_author,
                                # parent_comment_body, parent_comment_author
    voted_posts.csv             # id, permalink, direction + fetched_title,
                                # fetched_body, fetched_score, fetched_subreddit,
                                # fetched_author
    voted_comments.csv          # id, permalink, direction + fetched_body,
                                # fetched_score, fetched_subreddit, fetched_author
    saved_posts.csv             # id, permalink + fetched_title, fetched_body,
                                # fetched_score, fetched_subreddit, fetched_author
    external_links.csv          # source_type, source_id, source_subreddit,
                                # url, domain, category
    hydration_manifest.json     # Per-tier fetch stats, coverage, timestamps
  hydration_cache/              # Raw JSON responses keyed by URL (for debugging/reruns)
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Not deduplicating parent post URLs | Comments in the same thread share a parent — build unique URL set first |
| Constructing separate URLs for parent comments | The parent comment is in the post's comment tree JSON — search it there instead of making a new request |
| Ignoring `[deleted]` / `[removed]` body text | These are valid fetch results — record them, do not retry or mark as errors |
| Running Tier 2 before Tier 1 | Tier 1 (parent context) is the highest-value hydration — always complete it first |
| Not reporting coverage to downstream agents | Without the manifest, downstream agents do not know what percentage of records have context |
| Fetching from `old.reddit.com` | Use `www.reddit.com` for the `.json` trick — `old.reddit.com` may not support it consistently |
| Storing cache in the project root | Use `data/hydration_cache/` to keep fetched JSON separate from source data and enriched outputs |

## References

- [Reddit JSON API (unofficial)](https://www.reddit.com/dev/api/) — append `.json` to any permalink
- [Minet Documentation](https://github.com/medialab/minet) — URL parsing and web content extraction
- [Requests library: Timeouts](https://requests.readthedocs.io/en/latest/user/advanced/#timeouts)
- [Exponential Backoff and Jitter (AWS Architecture Blog)](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
