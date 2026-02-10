#!/usr/bin/env python3
"""Content Hydration Pipeline

Fetches linked content from Reddit GDPR export CSVs using the .json permalink trick.
Produces enriched CSVs in data/enriched/ for downstream analysis agents.

Tiers:
  1. Parent context for user's comments (parent post title/body + parent comment body)
  2. Voted/saved content (fetches post/comment content from permalinks)
  3. External URL catalog (extracts and classifies non-Reddit URLs, no fetching)

Usage:
  python scripts/hydrate.py                 # Run all tiers
  python scripts/hydrate.py --tier 1        # Run only Tier 1
  python scripts/hydrate.py --tier 2        # Run only Tier 2
  python scripts/hydrate.py --tier 3        # Run only Tier 3 (no network)
  python scripts/hydrate.py --status        # Show checkpoint status
"""

import csv
import json
import os
import re
import sys
import time
import hashlib
import argparse
import random
from pathlib import Path
from urllib.parse import urlparse
from collections import defaultdict

import requests

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
ENRICHED_DIR = BASE_DIR / "data" / "enriched"
CACHE_DIR = BASE_DIR / "data" / "hydration_cache"
CHECKPOINT_DIR = BASE_DIR / "data" / "checkpoints"
REPORT_PATH = BASE_DIR / "docs" / "analysis" / "02b-content-hydration.md"

# Source CSVs
COMMENTS_CSV = BASE_DIR / "comments.csv"
POSTS_CSV = BASE_DIR / "posts.csv"
POST_VOTES_CSV = BASE_DIR / "post_votes.csv"
COMMENT_VOTES_CSV = BASE_DIR / "comment_votes.csv"
SAVED_POSTS_CSV = BASE_DIR / "saved_posts.csv"

# Rate limiting
BASE_DELAY = 2.0  # seconds between requests
MAX_RETRIES = 4
USER_AGENT = "PersonaSynthesisPipeline/1.0 (content-hydration; research use)"

# Checkpointing
CHECKPOINT_INTERVAL = 25  # save checkpoint every N fetches


# ─── Directory Setup ─────────────────────────────────────────────────────────

def setup_dirs():
    for d in [ENRICHED_DIR, CACHE_DIR, CHECKPOINT_DIR]:
        d.mkdir(parents=True, exist_ok=True)


# ─── Disk Cache ──────────────────────────────────────────────────────────────

def cache_key(url):
    """Generate a filesystem-safe cache key from a URL."""
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    # Also keep a readable portion
    safe = re.sub(r'[^\w]', '_', url)[-80:]
    return f"{h}_{safe}"


def cache_path(url):
    return CACHE_DIR / f"{cache_key(url)}.json"


def cache_get(url):
    """Read cached JSON response, or None if not cached."""
    p = cache_path(url)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def cache_put(url, data):
    """Write JSON response to disk cache."""
    p = cache_path(url)
    try:
        p.write_text(json.dumps(data, ensure_ascii=False))
    except OSError as e:
        print(f"  [warn] Cache write failed for {url[:60]}: {e}")


# ─── Checkpointing ──────────────────────────────────────────────────────────

class Checkpoint:
    def __init__(self, name):
        self.path = CHECKPOINT_DIR / f"hydration_{name}.json"
        self.state = self._load()

    def _load(self):
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"fetched": [], "failed": [], "rate_limited_events": 0}

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2))
        tmp.rename(self.path)

    def is_done(self, url):
        return url in self.state["fetched"] or url in self.state["failed"]

    def mark_done(self, url):
        if url not in self.state["fetched"]:
            self.state["fetched"].append(url)

    def mark_failed(self, url):
        if url not in self.state["failed"]:
            self.state["failed"].append(url)

    @property
    def summary(self):
        return {
            "fetched": len(self.state["fetched"]),
            "failed": len(self.state["failed"]),
            "rate_limited_events": self.state.get("rate_limited_events", 0),
        }


# ─── HTTP Fetching ───────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def normalize_json_url(url):
    """Ensure URL ends with .json for Reddit API trick."""
    url = url.strip().rstrip("/")
    if not url.endswith(".json"):
        url += ".json"
    return url


def fetch_url(url, checkpoint, delay=BASE_DELAY):
    """Fetch a URL with rate limiting, retries, and caching.

    Returns parsed JSON data or None on failure.
    """
    # Check disk cache first (free, no network)
    cached = cache_get(url)
    if cached is not None:
        checkpoint.mark_done(url)
        return cached if not cached.get("_status") == "not_found" else None

    # Fetch with exponential backoff
    for attempt in range(MAX_RETRIES):
        time.sleep(delay if attempt == 0 else delay * (2 ** attempt) + random.uniform(0, 1))
        try:
            resp = session.get(url, timeout=15)

            if resp.status_code == 200:
                data = resp.json()
                cache_put(url, data)
                checkpoint.mark_done(url)
                return data

            elif resp.status_code in (429, 503):
                checkpoint.state["rate_limited_events"] = checkpoint.state.get("rate_limited_events", 0) + 1
                wait = delay * (2 ** (attempt + 1)) + random.uniform(0, 2)
                print(f"  [429/503] Rate limited. Backoff {wait:.1f}s (attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue

            elif resp.status_code == 404:
                cache_put(url, {"_status": "not_found"})
                checkpoint.mark_failed(url)
                return None

            else:
                if attempt == MAX_RETRIES - 1:
                    checkpoint.mark_failed(url)
                continue

        except requests.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                print(f"  [error] {url[:60]}: {e}")
                checkpoint.mark_failed(url)
                return None
            continue

    checkpoint.mark_failed(url)
    return None


# ─── JSON Parsing Helpers ────────────────────────────────────────────────────

def extract_post(data):
    """Extract post fields from Reddit .json response."""
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
            "num_comments": post.get("num_comments", 0),
            "upvote_ratio": post.get("upvote_ratio", 0),
        }
    except (KeyError, IndexError, TypeError):
        return None


def find_comment_in_tree(data, target_id):
    """Search the comment tree for a specific comment by ID.

    Reddit comment IDs in exports are bare (e.g., 'dlazu42').
    In JSON, 'id' is 'dlazu42' and 'name' is 't1_dlazu42'.
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
            replies = cdata.get("replies")
            if isinstance(replies, dict):
                result = _search(replies.get("data", {}).get("children", []))
                if result:
                    return result
        return None

    return _search(data[1]["data"]["children"])


def extract_comment_from_permalink(data):
    """Extract comment data from a comment-permalink .json response.

    When you fetch a comment permalink, [1] contains the comment's own tree
    with the target comment as the first child.
    """
    if not data or not isinstance(data, list) or len(data) < 2:
        return None
    try:
        children = data[1]["data"]["children"]
        if children and children[0].get("kind") == "t1":
            cdata = children[0]["data"]
            return {
                "body": cdata.get("body", ""),
                "author": cdata.get("author", "[unknown]"),
                "score": cdata.get("score", 0),
                "subreddit": cdata.get("subreddit", ""),
            }
    except (KeyError, IndexError, TypeError):
        pass
    return None


# ─── Tier 1: Parent Context ─────────────────────────────────────────────────

def run_tier1():
    """Enrich comments with parent post and parent comment context."""
    print("\n═══ Tier 1: Parent Context for Comments ═══")

    if not COMMENTS_CSV.exists():
        print("  [skip] comments.csv not found")
        return {"skipped": "no_source_file"}

    # Read comments
    with open(COMMENTS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        comments = list(reader)
    print(f"  Loaded {len(comments)} comments")

    # Step 1: Deduplicate parent post URLs
    url_to_comments = defaultdict(list)  # post_url -> [comment indices]
    for i, row in enumerate(comments):
        link = row.get("link", "").strip()
        if link:
            url_to_comments[link.rstrip("/")].append(i)

    unique_post_urls = list(url_to_comments.keys())
    print(f"  {len(unique_post_urls)} unique parent post URLs (deduped from {len(comments)} comments)")

    # Step 2: Fetch parent posts
    checkpoint = Checkpoint("tier1")
    post_cache = {}  # url -> {title, body, ...}
    json_cache = {}  # url -> raw JSON (for comment tree search)

    to_fetch = [u for u in unique_post_urls if not checkpoint.is_done(normalize_json_url(u))]
    already = len(unique_post_urls) - len(to_fetch)
    if already > 0:
        print(f"  Resuming: {already} already fetched, {len(to_fetch)} remaining")

    # Load cached data for already-fetched URLs
    for url in unique_post_urls:
        json_url = normalize_json_url(url)
        cached = cache_get(json_url)
        if cached and not cached.get("_status"):
            post_cache[url] = extract_post(cached)
            json_cache[url] = cached

    for i, url in enumerate(to_fetch):
        json_url = normalize_json_url(url)
        print(f"  [{already + i + 1}/{len(unique_post_urls)}] {url[:70]}...")
        data = fetch_url(json_url, checkpoint)
        if data and not data.get("_status"):
            post_cache[url] = extract_post(data)
            json_cache[url] = data
        if (i + 1) % CHECKPOINT_INTERVAL == 0:
            checkpoint.save()

    checkpoint.save()
    print(f"  Posts fetched: {len(post_cache)}/{len(unique_post_urls)}")

    # Step 3: Resolve parent comments from cached post trees
    parent_comment_cache = {}  # (post_url, parent_id) -> {body, author, ...}
    parent_lookups = 0
    parent_found = 0

    for row in comments:
        link = row.get("link", "").strip().rstrip("/")
        parent_id = row.get("parent", "").strip()
        if not link or not parent_id:
            continue
        if parent_id == row.get("id", "").strip():
            continue  # top-level comment, parent is the post itself

        key = (link, parent_id)
        if key in parent_comment_cache:
            continue

        parent_lookups += 1
        tree_data = json_cache.get(link)
        if tree_data:
            result = find_comment_in_tree(tree_data, parent_id)
            parent_comment_cache[key] = result
            if result:
                parent_found += 1

    print(f"  Parent comments: {parent_found}/{parent_lookups} found in post trees")

    # Step 4: Write enriched CSV
    output_path = ENRICHED_DIR / "comments_with_context.csv"
    fieldnames = list(comments[0].keys()) + [
        "parent_post_title", "parent_post_body", "parent_post_author",
        "parent_post_score", "parent_comment_body", "parent_comment_author"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in comments:
            link = row.get("link", "").strip().rstrip("/")
            parent_id = row.get("parent", "").strip()

            post = post_cache.get(link) or {}
            row["parent_post_title"] = post.get("title", "")
            row["parent_post_body"] = post.get("body", "")
            row["parent_post_author"] = post.get("author", "")
            row["parent_post_score"] = post.get("score", "")

            pcomment = parent_comment_cache.get((link, parent_id)) or {}
            row["parent_comment_body"] = pcomment.get("body", "")
            row["parent_comment_author"] = pcomment.get("author", "")

            writer.writerow(row)

    print(f"  Output: {output_path}")

    return {
        **checkpoint.summary,
        "unique_post_urls": len(unique_post_urls),
        "posts_fetched": len(post_cache),
        "parent_comments_resolved": parent_found,
        "parent_comments_attempted": parent_lookups,
    }


# ─── Tier 2: Voted / Saved Content ──────────────────────────────────────────

def run_tier2_post_votes():
    """Fetch content for voted posts."""
    print("\n═══ Tier 2a: Post Votes ═══")

    if not POST_VOTES_CSV.exists():
        print("  [skip] post_votes.csv not found")
        return {"skipped": "no_source_file"}

    with open(POST_VOTES_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("  [skip] post_votes.csv is empty")
        return {"skipped": "empty_input"}

    print(f"  Loaded {len(rows)} post votes")

    checkpoint = Checkpoint("tier2_post_votes")

    # Deduplicate URLs
    url_set = {}  # url -> first row index
    for i, row in enumerate(rows):
        url = row.get("permalink", "").strip().rstrip("/")
        if url and url not in url_set:
            url_set[url] = i

    unique_urls = list(url_set.keys())
    to_fetch = [u for u in unique_urls if not checkpoint.is_done(normalize_json_url(u))]
    already = len(unique_urls) - len(to_fetch)
    if already > 0:
        print(f"  Resuming: {already} cached, {len(to_fetch)} remaining")

    results = {}

    # Load from cache
    for url in unique_urls:
        cached = cache_get(normalize_json_url(url))
        if cached and not cached.get("_status"):
            results[url] = extract_post(cached)

    for i, url in enumerate(to_fetch):
        json_url = normalize_json_url(url)
        print(f"  [{already + i + 1}/{len(unique_urls)}] {url[:70]}...")
        data = fetch_url(json_url, checkpoint)
        if data and not data.get("_status"):
            results[url] = extract_post(data)
        if (i + 1) % CHECKPOINT_INTERVAL == 0:
            checkpoint.save()

    checkpoint.save()
    print(f"  Fetched: {len(results)}/{len(unique_urls)}")

    # Write enriched CSV
    output_path = ENRICHED_DIR / "voted_posts.csv"
    fieldnames = list(rows[0].keys()) + [
        "fetched_title", "fetched_body", "fetched_score",
        "fetched_subreddit", "fetched_author", "fetched_upvote_ratio"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            url = row.get("permalink", "").strip().rstrip("/")
            post = results.get(url) or {}
            row["fetched_title"] = post.get("title", "")
            row["fetched_body"] = post.get("body", "")
            row["fetched_score"] = post.get("score", "")
            row["fetched_subreddit"] = post.get("subreddit", "")
            row["fetched_author"] = post.get("author", "")
            row["fetched_upvote_ratio"] = post.get("upvote_ratio", "")
            writer.writerow(row)

    print(f"  Output: {output_path}")
    return {**checkpoint.summary, "unique_urls": len(unique_urls), "posts_fetched": len(results)}


def run_tier2_comment_votes():
    """Fetch content for voted comments."""
    print("\n═══ Tier 2b: Comment Votes ═══")

    if not COMMENT_VOTES_CSV.exists():
        print("  [skip] comment_votes.csv not found")
        return {"skipped": "no_source_file"}

    with open(COMMENT_VOTES_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("  [skip] comment_votes.csv is empty")
        return {"skipped": "empty_input"}

    print(f"  Loaded {len(rows)} comment votes")

    checkpoint = Checkpoint("tier2_comment_votes")

    # Deduplicate URLs
    url_set = {}
    for i, row in enumerate(rows):
        url = row.get("permalink", "").strip().rstrip("/")
        if url and url not in url_set:
            url_set[url] = i

    unique_urls = list(url_set.keys())
    to_fetch = [u for u in unique_urls if not checkpoint.is_done(normalize_json_url(u))]
    already = len(unique_urls) - len(to_fetch)
    if already > 0:
        print(f"  Resuming: {already} cached, {len(to_fetch)} remaining")

    results = {}

    # Load from cache
    for url in unique_urls:
        cached = cache_get(normalize_json_url(url))
        if cached and not cached.get("_status"):
            results[url] = extract_comment_from_permalink(cached)

    for i, url in enumerate(to_fetch):
        json_url = normalize_json_url(url)
        print(f"  [{already + i + 1}/{len(unique_urls)}] {url[:70]}...")
        data = fetch_url(json_url, checkpoint)
        if data and not data.get("_status"):
            results[url] = extract_comment_from_permalink(data)
        if (i + 1) % CHECKPOINT_INTERVAL == 0:
            checkpoint.save()

    checkpoint.save()
    print(f"  Fetched: {len(results)}/{len(unique_urls)}")

    # Write enriched CSV
    output_path = ENRICHED_DIR / "voted_comments.csv"
    fieldnames = list(rows[0].keys()) + [
        "fetched_body", "fetched_score", "fetched_subreddit", "fetched_author"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            url = row.get("permalink", "").strip().rstrip("/")
            comment = results.get(url) or {}
            row["fetched_body"] = comment.get("body", "")
            row["fetched_score"] = comment.get("score", "")
            row["fetched_subreddit"] = comment.get("subreddit", "")
            row["fetched_author"] = comment.get("author", "")
            writer.writerow(row)

    print(f"  Output: {output_path}")
    return {**checkpoint.summary, "unique_urls": len(unique_urls), "comments_fetched": len(results)}


def run_tier2_saved():
    """Fetch content for saved posts."""
    print("\n═══ Tier 2c: Saved Posts ═══")

    if not SAVED_POSTS_CSV.exists():
        print("  [skip] saved_posts.csv not found")
        return {"skipped": "no_source_file"}

    with open(SAVED_POSTS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("  [skip] saved_posts.csv is empty")
        return {"skipped": "empty_input"}

    print(f"  Loaded {len(rows)} saved posts")

    checkpoint = Checkpoint("tier2_saved")

    url_set = {}
    for i, row in enumerate(rows):
        url = row.get("permalink", "").strip().rstrip("/")
        if url and url not in url_set:
            url_set[url] = i

    unique_urls = list(url_set.keys())
    to_fetch = [u for u in unique_urls if not checkpoint.is_done(normalize_json_url(u))]

    results = {}
    for url in unique_urls:
        cached = cache_get(normalize_json_url(url))
        if cached and not cached.get("_status"):
            results[url] = extract_post(cached)

    for i, url in enumerate(to_fetch):
        json_url = normalize_json_url(url)
        print(f"  [{i + 1}/{len(to_fetch)}] {url[:70]}...")
        data = fetch_url(json_url, checkpoint)
        if data and not data.get("_status"):
            results[url] = extract_post(data)

    checkpoint.save()
    print(f"  Fetched: {len(results)}/{len(unique_urls)}")

    output_path = ENRICHED_DIR / "saved_posts.csv"
    fieldnames = list(rows[0].keys()) + [
        "fetched_title", "fetched_body", "fetched_score",
        "fetched_subreddit", "fetched_author"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            url = row.get("permalink", "").strip().rstrip("/")
            post = results.get(url) or {}
            row["fetched_title"] = post.get("title", "")
            row["fetched_body"] = post.get("body", "")
            row["fetched_score"] = post.get("score", "")
            row["fetched_subreddit"] = post.get("subreddit", "")
            row["fetched_author"] = post.get("author", "")
            writer.writerow(row)

    print(f"  Output: {output_path}")
    return {**checkpoint.summary, "unique_urls": len(unique_urls), "posts_fetched": len(results)}


# ─── Tier 3: External URL Catalog ───────────────────────────────────────────

URL_PATTERN = re.compile(r'https?://[^\s\)\]\>\"\'`,;\<]+', re.IGNORECASE)

DOMAIN_CATEGORIES = {
    "youtube.com": "video", "youtu.be": "video", "vimeo.com": "video",
    "github.com": "code", "gitlab.com": "code", "bitbucket.org": "code",
    "stackoverflow.com": "code", "stackexchange.com": "code",
    "imgur.com": "image", "i.redd.it": "image", "i.imgur.com": "image",
    "flickr.com": "image",
    "twitter.com": "social", "x.com": "social",
    "wikipedia.org": "reference", "en.wikipedia.org": "reference",
    "arxiv.org": "academic", "doi.org": "academic", "scholar.google.com": "academic",
    "docs.google.com": "document", "drive.google.com": "document",
    "maps.google.com": "map", "goo.gl": "shortlink",
    "kaggle.com": "data",
    "play.google.com": "app", "apps.apple.com": "app",
}


def classify_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().lstrip("www.")
        if domain in DOMAIN_CATEGORIES:
            return DOMAIN_CATEGORIES[domain]
        full = domain + parsed.path.lower()
        for pattern, cat in DOMAIN_CATEGORIES.items():
            if pattern in full:
                return cat
        return "other"
    except Exception:
        return "unknown"


def run_tier3():
    """Extract and classify external URLs from post and comment bodies."""
    print("\n═══ Tier 3: External URL Catalog ═══")

    records = []

    for source_path, source_type in [(POSTS_CSV, "post"), (COMMENTS_CSV, "comment")]:
        if not source_path.exists():
            print(f"  [skip] {source_path.name} not found")
            continue

        with open(source_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        for row in rows:
            text = row.get("body", "")
            urls = URL_PATTERN.findall(text)
            for url in urls:
                url = url.rstrip(".,;:!?)")
                try:
                    parsed = urlparse(url)
                except Exception:
                    continue
                # Skip Reddit internal links
                if any(d in parsed.netloc.lower() for d in ["reddit.com", "redd.it"]):
                    continue
                records.append({
                    "source_type": source_type,
                    "source_id": row.get("id", ""),
                    "source_subreddit": row.get("subreddit", ""),
                    "url": url,
                    "domain": parsed.netloc.lower().lstrip("www."),
                    "category": classify_domain(url),
                })

    # Deduplicate on (url, source_id)
    seen = set()
    deduped = []
    for r in records:
        key = (r["url"], r["source_id"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    output_path = ENRICHED_DIR / "external_links.csv"
    if deduped:
        fieldnames = ["source_type", "source_id", "source_subreddit", "url", "domain", "category"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(deduped)
    else:
        output_path.write_text("source_type,source_id,source_subreddit,url,domain,category\n")

    # Domain summary
    domain_counts = defaultdict(int)
    category_counts = defaultdict(int)
    for r in deduped:
        domain_counts[r["domain"]] += 1
        category_counts[r["category"]] += 1

    print(f"  Total external URLs: {len(records)}")
    print(f"  Unique (url, source): {len(deduped)}")
    print(f"  Top domains:")
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    {domain}: {count}")
    print(f"  Categories:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")
    print(f"  Output: {output_path}")

    return {
        "total_urls": len(records),
        "unique_urls": len(deduped),
        "domains": dict(domain_counts),
        "categories": dict(category_counts),
    }


# ─── Manifest ────────────────────────────────────────────────────────────────

def write_manifest(tier_results):
    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "complete",
        "tiers": {},
    }

    for tier_name, result in tier_results.items():
        if result.get("skipped"):
            manifest["tiers"][tier_name] = {"skipped": result["skipped"]}
            continue

        fetched = result.get("fetched", 0)
        failed = result.get("failed", 0)
        total = fetched + failed

        entry = {
            "total_urls": total,
            "fetched": fetched,
            "failed": failed,
            "rate_limited_events": result.get("rate_limited_events", 0),
            "coverage_pct": round(fetched / total * 100, 1) if total else 0,
        }

        # Tier-specific extras
        for key in ["unique_post_urls", "posts_fetched", "parent_comments_resolved",
                     "parent_comments_attempted", "unique_urls", "comments_fetched",
                     "total_urls", "unique_urls", "domains", "categories"]:
            if key in result and key not in entry:
                entry[key] = result[key]

        manifest["tiers"][tier_name] = entry

        if failed > 0:
            manifest["status"] = "partial"

    manifest_path = ENRICHED_DIR / "hydration_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\n  Manifest: {manifest_path}")
    return manifest


# ─── Report ──────────────────────────────────────────────────────────────────

def write_report(manifest, tier_results):
    t1 = tier_results.get("tier1_parent_context", {})
    t2a = tier_results.get("tier2_post_votes", {})
    t2b = tier_results.get("tier2_comment_votes", {})
    t2c = tier_results.get("tier2_saved_posts", {})
    t3 = tier_results.get("tier3_external_urls", {})

    def _row(label, result):
        if result.get("skipped"):
            return f"| {label} | — | — | — | skipped: {result['skipped']} |"
        f = result.get("fetched", 0)
        fail = result.get("failed", 0)
        total = f + fail
        pct = f"{round(f / total * 100, 1)}%" if total else "—"
        return f"| {label} | {total} | {f} | {fail} | {pct} |"

    # Domain/category summary for Tier 3
    domain_lines = ""
    if t3.get("domains"):
        top = sorted(t3["domains"].items(), key=lambda x: -x[1])[:15]
        domain_lines = "\n".join(f"| {d} | {c} |" for d, c in top)

    cat_lines = ""
    if t3.get("categories"):
        cat_lines = "\n".join(
            f"| {c} | {n} |"
            for c, n in sorted(t3["categories"].items(), key=lambda x: -x[1])
        )

    report = f"""# Content Hydration Report

## Configuration
- Source files: comments.csv, posts.csv, post_votes.csv, comment_votes.csv, saved_posts.csv
- Fetch method: Reddit .json permalink trick (append .json to any Reddit URL)
- Rate limit: {BASE_DELAY}s baseline, exponential backoff on 429/503
- User-Agent: {USER_AGENT}
- Generated: {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

## Tier 1: Parent Context

Enriched user comments with the parent post (title, body, author, score) and parent comment
(body, author) that the user was replying to.

- Unique parent post URLs: {t1.get("unique_post_urls", "—")}
- Posts fetched: {t1.get("posts_fetched", "—")}
- Parent comments resolved from post trees: {t1.get("parent_comments_resolved", "—")} of {t1.get("parent_comments_attempted", "—")}
- Rate limit events: {t1.get("rate_limited_events", 0)}
- Output: `data/enriched/comments_with_context.csv`

## Tier 2: Voted / Saved Content

### Post Votes
- URLs: {t2a.get("unique_urls", "—")}, Fetched: {t2a.get("posts_fetched", "—")}
- Rate limit events: {t2a.get("rate_limited_events", 0)}
- Output: `data/enriched/voted_posts.csv`

### Comment Votes
- URLs: {t2b.get("unique_urls", "—")}, Fetched: {t2b.get("comments_fetched", "—")}
- Rate limit events: {t2b.get("rate_limited_events", 0)}
- Output: `data/enriched/voted_comments.csv`

### Saved Posts
- URLs: {t2c.get("unique_urls", "—")}, Fetched: {t2c.get("posts_fetched", "—")}
- Rate limit events: {t2c.get("rate_limited_events", 0)}
- Output: `data/enriched/saved_posts.csv`

## Tier 3: External URL Catalog

Extracted and classified all non-Reddit URLs from post and comment body text.
No external content was fetched — URLs are cataloged by domain and category only.

- Total external URLs found: {t3.get("total_urls", "—")}
- Unique (url, source) pairs: {t3.get("unique_urls", "—")}
- Output: `data/enriched/external_links.csv`

### Top Domains

| Domain | Count |
|--------|-------|
{domain_lines}

### Category Distribution

| Category | Count |
|----------|-------|
{cat_lines}

## Fetch Summary

| Tier | Total URLs | Fetched | Failed | Coverage |
|------|-----------|---------|--------|----------|
{_row("1 — Parent Context", t1)}
{_row("2a — Post Votes", t2a)}
{_row("2b — Comment Votes", t2b)}
{_row("2c — Saved Posts", t2c)}
| 3 — External Catalog | {t3.get("unique_urls", "—")} | — | — | cataloged |

## Data Quality Notes

- Deleted content (`[deleted]`/`[removed]`) is recorded as successful fetches with the deletion marker intact
- Parent comments not found in the top-level comment tree may be deeply nested or deleted
- Rate limit events indicate Reddit throttling; data was still collected via backoff/retry
- Overall hydration status: **{manifest.get("status", "unknown")}**

## Recommendations for Downstream Analysis

- **Prefer enriched data**: Downstream agents should read from `data/enriched/` instead of raw CSVs
- `comments_with_context.csv` adds parent post/comment columns — critical for sentiment, speech act, network, and CAT/LSM analyses
- `voted_posts.csv` and `voted_comments.csv` reveal engagement preferences even for non-authored content
- `external_links.csv` provides interest signals from shared URLs (domain categories)
- Check `hydration_manifest.json` for coverage percentages before relying on enriched fields
"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print(f"  Report: {REPORT_PATH}")


# ─── Status ──────────────────────────────────────────────────────────────────

def show_status():
    """Show checkpoint status for all tiers."""
    print("\n═══ Hydration Checkpoint Status ═══\n")

    manifest_path = ENRICHED_DIR / "hydration_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        print(f"  Last run: {manifest.get('generated_at', 'unknown')}")
        print(f"  Status: {manifest.get('status', 'unknown')}")
        print()

    for name in ["tier1", "tier2_post_votes", "tier2_comment_votes", "tier2_saved", "tier3"]:
        cp_path = CHECKPOINT_DIR / f"hydration_{name}.json"
        if cp_path.exists():
            state = json.loads(cp_path.read_text())
            f = len(state.get("fetched", []))
            fail = len(state.get("failed", []))
            rl = state.get("rate_limited_events", 0)
            print(f"  {name}: fetched={f}, failed={fail}, rate_limits={rl}")
        else:
            print(f"  {name}: no checkpoint")

    # Check enriched files
    print()
    for f in ["comments_with_context.csv", "voted_posts.csv", "voted_comments.csv",
              "saved_posts.csv", "external_links.csv", "hydration_manifest.json"]:
        p = ENRICHED_DIR / f
        if p.exists():
            size = p.stat().st_size
            print(f"  {f}: {size:,} bytes")
        else:
            print(f"  {f}: missing")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Content Hydration Pipeline")
    parser.add_argument("--tier", type=str, help="Run only this tier (1, 2, 3)")
    parser.add_argument("--status", action="store_true", help="Show checkpoint status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    setup_dirs()

    tier_results = {}
    start = time.time()

    if args.tier is None or args.tier == "1":
        tier_results["tier1_parent_context"] = run_tier1()

    if args.tier is None or args.tier == "2":
        tier_results["tier2_post_votes"] = run_tier2_post_votes()
        tier_results["tier2_comment_votes"] = run_tier2_comment_votes()
        tier_results["tier2_saved_posts"] = run_tier2_saved()

    if args.tier is None or args.tier == "3":
        tier_results["tier3_external_urls"] = run_tier3()

    elapsed = time.time() - start
    print(f"\n═══ Complete ({elapsed:.0f}s) ═══")

    manifest = write_manifest(tier_results)
    write_report(manifest, tier_results)


if __name__ == "__main__":
    main()
