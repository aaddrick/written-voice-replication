---
name: mdpi-hypernetwork-archetype
description: Use when classifying users or accounts along Score, Sentiment, and Toxicity axes into behavioral archetypes (HHH through LLL), analyzing engagement patterns in online community data, combining visibility/influence with affective and toxicity dimensions, or needing to assign behavioral archetype labels from multi-axis normalized user metrics
---

# MDPI Social Hypernetwork Archetype Classification

## Overview

Classify users into one of eight behavioral archetypes by scoring them on three normalized axes -- Score (visibility/influence), Sentiment (affective valence), and Toxicity (harmful language probability) -- then assigning a three-letter label (High/Low on each axis) that describes their engagement pattern. The core principle: **archetypes are behavioral patterns observable in data, not personality types or stable traits -- they describe what a user does in a given period, not who they are.**

This methodology is based on Ferrara et al. (2025), "Characterizing User Archetypes and Discussions on Social Hypernetworks" (MDPI Big Data and Cognitive Computing, 9(9), 236), which introduced the three-axis archetype framework for characterizing nodes in social hypernetworks.

## When to Use

- User-generated content corpus with at least post/comment text and some form of engagement score
- Need to segment users by behavioral pattern rather than a single metric
- Want to understand the interplay between visibility, sentiment, and toxicity in a community
- Analyzing community health, moderation needs, or engagement dynamics
- Preparing user profiles for downstream style analysis where emotional valence constraints matter

**When NOT to use:**

- Corpus has fewer than 30 users (archetypes require distributional reasoning)
- Only one axis of data is available (use single-metric analysis instead)
- Goal is to psychologically profile individuals (archetypes describe behavior, not personality)
- Classifying bots or automated accounts (behavioral patterns differ fundamentally)
- Comparing archetypes across platforms without recalibrating thresholds per platform

## Quick Reference: The Eight Archetypes

The three-letter code follows the order **Score-Sentiment-Toxicity**, where H = High and L = Low.

| Archetype | Score | Sentiment | Toxicity | Behavioral Signature | Emotional Valence Constraints |
|-----------|-------|-----------|----------|---------------------|-------------------------------|
| **HHH** | High | High | High | High-visibility, positive-leaning, yet confrontational. Influential users who express positive sentiment but deploy toxic language (profanity, aggressive rhetoric) as emphasis. Emotionally charged engagement -- happiness coexists with anger. | Positive base with aggressive punctuation; high arousal |
| **HHL** | High | High | Low | High-visibility, positive, constructive. The "model citizen" archetype -- consistently upvoted, positive tone, non-toxic. Associated with trust, joy, and anticipation. Most stable archetype over time. | Positive, measured, low arousal; supportive register |
| **HLH** | High | Low | High | High-visibility, negative, toxic. Prominent critics who combine harsh sentiment with toxic language. High-profile antagonists whose negativity draws engagement. | Negative, aggressive, high arousal; combative register |
| **HLL** | High | Low | Low | High-visibility, negative, non-toxic. Influential skeptics or critical analysts. Negative sentiment expressed through substantive criticism rather than toxicity. | Negative but restrained; analytical or disappointed register |
| **LHH** | Low | High | High | Low-visibility, positive, yet toxic. Positive disposition executed through confrontational style. Supportive intent with aggressive delivery -- "tough love" communicators. | Positive intent, aggressive delivery; mixed signals |
| **LHL** | Low | High | Low | Low-visibility, positive, non-toxic. Quiet supporters and encouragers. Low engagement scores but consistently positive, constructive contributions. | Positive, gentle, low arousal; encouraging register |
| **LLH** | Low | Low | High | Low-visibility, negative, toxic. Discontented, marginalized antagonists. Negative affect combined with toxic language but without community traction. Most disruptive archetype. | Negative, hostile, high arousal; bitter or resentful register |
| **LLL** | Low | Low | Low | Low-visibility, negative, non-toxic. Quiet critics. Unhappy but not confrontational -- express dissatisfaction through measured, low-engagement commentary. | Negative but subdued; withdrawn or resigned register |

## Workflow

Copy this checklist and track progress:

```
MDPI Hypernetwork Archetype Classification Progress:
- [ ] Step 1: Validate corpus suitability and axis availability
- [ ] Step 2: Compute and normalize Score axis
- [ ] Step 3: Compute and normalize Sentiment axis
- [ ] Step 4: Compute and normalize Toxicity axis
- [ ] Step 5: Determine and document High/Low thresholds
- [ ] Step 6: Assign archetype labels
- [ ] Step 7: Compute typicality scores
- [ ] Step 8: Analyze archetype distributions and validate
- [ ] Step 9: Write findings to docs/analysis/14-mdpi-hypernetwork-archetype.md
```

### Step 1: Validate Corpus Suitability and Axis Availability

Before classification, confirm that the corpus supports all three axes.

**Axis requirements:**

| Axis | Required Data | Minimum Signal | Fallback if Missing |
|------|--------------|----------------|---------------------|
| **Score** | Numeric engagement metric (votes, points, likes, karma) | At least 70% of users have a computable score | Cannot proceed without at least one engagement metric; use binary active/inactive as last resort |
| **Sentiment** | Text content scorable by VADER or equivalent | At least 50 texts per user (median), or at least 5 texts per user with corpus > 100 users | See Two-Axis Fallback below |
| **Toxicity** | Text content scorable by Detoxify, Perspective API, or equivalent | Same as sentiment | See Two-Axis Fallback below |

**Corpus size minimums:**

| Corpus Size | Viability |
|-------------|-----------|
| < 30 users | Do NOT classify. Report individual user metrics without archetype assignment. |
| 30-99 users | Classify but flag all results as low-confidence. Some archetypes may have < 5 members, making them unreliable. |
| 100-499 users | Adequate. Expect some archetypes to be sparsely populated. |
| 500+ users | Full analysis viable. All eight archetypes should be meaningfully populated. |

```python
import pandas as pd
import numpy as np

# Check axis availability
required_axes = {
    'score': ['score', 'points', 'karma', 'votes', 'ups'],
    'sentiment': ['compound', 'sentiment_compound', 'vader_compound'],
    'toxicity': ['toxicity', 'toxic_score', 'detoxify_score', 'perspective_score'],
}

for axis, candidate_cols in required_axes.items():
    found = [c for c in candidate_cols if c in df.columns]
    coverage = df[found[0]].notna().mean() * 100 if found else 0
    print(f"{axis}: columns={found or 'MISSING'}, coverage={coverage:.1f}%")
```

### Step 2: Compute and Normalize Score Axis

The Score axis measures user visibility and influence within the community. It is typically computed as the mean engagement score across a user's content.

**Computation:**

```python
def compute_user_score(user_df, score_col='score'):
    """Compute per-user mean score from their content."""
    user_scores = user_df.groupby('author')[score_col].mean()
    return user_scores

user_scores = compute_user_score(content_df)
```

**Normalization to [0, 1]:**

Score distributions in online communities follow power laws (heavy right skew). Use log-transform then min-max normalization.

```python
def normalize_score_axis(user_scores):
    """Normalize user scores to [0, 1] using log-transform + min-max."""
    log_scores = np.log1p(user_scores - user_scores.min())  # Shift to non-negative, then log
    mn, mx = log_scores.min(), log_scores.max()
    if mx == mn:
        return pd.Series(0.5, index=log_scores.index)
    return (log_scores - mn) / (mx - mn)

norm_scores = normalize_score_axis(user_scores)
```

**Alternative normalization methods:**

| Method | When to Use |
|--------|-------------|
| Log min-max | Default for score axes; handles power-law distributions |
| Rank-based (`rank / N`) | When log-transform still leaves extreme outliers |
| Robust percentile (5th/95th) | When a few extreme users dominate even after log-transform |

### Step 3: Compute and Normalize Sentiment Axis

The Sentiment axis captures the affective valence of a user's content. Use VADER compound scores as the default scorer for informal/social media text.

**REQUIRED SUB-SKILL:** Use vader-sentiment-analysis for preprocessing and scoring.

**Computation:**

```python
from nltk.sentiment.vader import SentimentIntensityAnalyzer

sia = SentimentIntensityAnalyzer()

def compute_user_sentiment(user_df, text_col='body'):
    """Score each text, then average per user."""
    user_df = user_df.copy()
    user_df['compound'] = user_df[text_col].apply(
        lambda t: sia.polarity_scores(str(t))['compound'] if pd.notna(t) else np.nan
    )
    return user_df.groupby('author')['compound'].mean()

user_sentiment = compute_user_sentiment(content_df)
```

**Normalization:** VADER compound is in [-1, +1]. Shift to [0, 1]:

```python
norm_sentiment = (user_sentiment + 1) / 2  # [-1, +1] -> [0, 1]
```

### Step 4: Compute and Normalize Toxicity Axis

The Toxicity axis captures the probability that a user's language contains toxic content. This is **independent** of sentiment -- a comment can be positive in sentiment but toxic in delivery (profanity, slurs used casually), or negative in sentiment but non-toxic (substantive criticism).

**Recommended classifiers (in order of preference):**

| Classifier | Model | Output | Notes |
|------------|-------|--------|-------|
| **Detoxify** | `unitary/toxic-bert` | P(toxic) in [0, 1] | Multilabel (toxic, severe_toxic, obscene, threat, insult, identity_hate). Use the `toxicity` score. |
| **Perspective API** | Jigsaw/Google | P(toxic) in [0, 1] | Rate-limited; scores are probability estimates, not severity. |
| **Custom classifier** | Varies | Varies | Must be calibrated to output [0, 1] probability. Document model and calibration. |

**Critical distinction:** Toxicity is NOT the inverse of sentiment. These measure different constructs:

| | Positive Sentiment | Negative Sentiment |
|---|---|---|
| **High Toxicity** | "Hell yeah, that's f***ing awesome!" (HHH/LHH) | "You're an absolute moron" (HLH/LLH) |
| **Low Toxicity** | "I really appreciate this contribution" (HHL/LHL) | "I disagree with this analysis" (HLL/LLL) |

**Computation:**

```python
from detoxify import Detoxify

model = Detoxify('original')  # or 'unbiased' for reduced identity-term bias

def compute_user_toxicity(user_df, text_col='body'):
    """Score each text for toxicity, then average per user."""
    texts = user_df[text_col].fillna('').tolist()
    results = model.predict(texts)
    user_df = user_df.copy()
    user_df['toxicity'] = results['toxicity']
    return user_df.groupby('author')['toxicity'].mean()

user_toxicity = compute_user_toxicity(content_df)
```

**Normalization:** Detoxify and Perspective API both output [0, 1] probability. Verify the range in your corpus and apply min-max within the observed range if the corpus occupies a narrow band:

```python
def normalize_toxicity_axis(user_toxicity):
    """Normalize to [0, 1]. Usually already in [0, 1] from classifier."""
    mn, mx = user_toxicity.min(), user_toxicity.max()
    if mx == mn:
        return pd.Series(0.5, index=user_toxicity.index)
    if mn >= 0 and mx <= 1 and (mx - mn) > 0.3:
        return user_toxicity  # Already well-spread in [0, 1]
    # Re-normalize within observed range to use full [0, 1] span
    return (user_toxicity - mn) / (mx - mn)

norm_toxicity = normalize_toxicity_axis(user_toxicity)
```

**Community-specific threshold considerations:**

Toxicity classifiers are trained on general corpora. Some communities use language that scores as "toxic" but is normative within that context (e.g., gaming communities, certain fandoms, communities where profanity is casual). Document this when it applies. Do NOT adjust the classifier output to match community norms -- instead, note the discrepancy in the report and let the High/Low threshold (Step 5) handle it via the median split.

### Step 5: Determine and Document High/Low Thresholds

Each axis is split into High and Low using a threshold. The reference methodology (Ferrara et al., 2025) uses **0.5** on the normalized [0, 1] scale as the uniform threshold.

**Threshold options:**

| Method | Threshold | When to Use | Rationale |
|--------|-----------|-------------|-----------|
| **Fixed 0.5** (reference default) | 0.5 on [0, 1] | When normalized distributions are roughly symmetric around 0.5 | Directly comparable to the reference methodology |
| **Corpus median** | `median(axis)` | When distributions are skewed even after normalization | Guarantees approximately equal High/Low groups; robust to skew |
| **Domain-informed** | Varies | When external standards exist (e.g., Perspective API recommends 0.7 for toxicity) | Aligns with established practice in the field |

**Recommended approach:** Start with the 0.5 threshold to replicate the reference methodology. If more than 80% of users fall on one side of 0.5 for any axis, switch to median-based splitting for that axis and document the deviation.

```python
def compute_thresholds(norm_scores, norm_sentiment, norm_toxicity, method='fixed'):
    """Compute High/Low thresholds for each axis.
    method: 'fixed' (0.5), 'median', or 'domain'"""
    thresholds = {}
    axes = {
        'score': norm_scores,
        'sentiment': norm_sentiment,
        'toxicity': norm_toxicity,
    }

    for name, values in axes.items():
        if method == 'fixed':
            threshold = 0.5
        elif method == 'median':
            threshold = values.median()
        elif method == 'domain':
            # Domain-specific: use higher toxicity threshold
            threshold = 0.7 if name == 'toxicity' else 0.5
        else:
            raise ValueError(f"Unknown method: {method}")

        pct_high = (values >= threshold).mean() * 100
        pct_low = (values < threshold).mean() * 100

        # Auto-switch to median if fixed threshold produces extreme imbalance
        if method == 'fixed' and (pct_high > 80 or pct_low > 80):
            print(f"WARNING: {name} axis has {max(pct_high, pct_low):.0f}% on one side "
                  f"with fixed threshold. Switching to median for this axis.")
            threshold = values.median()
            pct_high = (values >= threshold).mean() * 100
            pct_low = (values < threshold).mean() * 100

        thresholds[name] = {
            'threshold': threshold,
            'method': method if not (method == 'fixed' and (pct_high > 80 or pct_low > 80)) else 'median (auto)',
            'pct_high': pct_high,
            'pct_low': pct_low,
        }

    return thresholds
```

**Document every threshold decision.** The report MUST include: the method used, the threshold value, the percentage of users in High vs. Low, and why the method was chosen.

### Step 6: Assign Archetype Labels

```python
def assign_archetypes(norm_scores, norm_sentiment, norm_toxicity, thresholds):
    """Assign three-letter archetype label to each user."""
    users = pd.DataFrame({
        'norm_score': norm_scores,
        'norm_sentiment': norm_sentiment,
        'norm_toxicity': norm_toxicity,
    }).dropna()

    users['score_label'] = np.where(
        users['norm_score'] >= thresholds['score']['threshold'], 'H', 'L'
    )
    users['sentiment_label'] = np.where(
        users['norm_sentiment'] >= thresholds['sentiment']['threshold'], 'H', 'L'
    )
    users['toxicity_label'] = np.where(
        users['norm_toxicity'] >= thresholds['toxicity']['threshold'], 'H', 'L'
    )

    users['archetype'] = (
        users['score_label'] + users['sentiment_label'] + users['toxicity_label']
    )

    return users
```

**Validation after assignment:**

```python
# Check archetype distribution
arch_counts = users['archetype'].value_counts()
print("Archetype distribution:")
print(arch_counts)
print(f"\nTotal users classified: {len(users)}")
print(f"Archetypes with < 5 members: {(arch_counts < 5).sum()}")
```

If any archetype has fewer than 5 members, flag it as low-confidence in the report. If more than 3 archetypes are empty, the corpus may lack sufficient behavioral diversity for this analysis -- document this limitation.

### Step 7: Compute Typicality Scores

Typicality measures how well a user exemplifies their assigned archetype. Users with high typicality are strongly representative; users near the thresholds are weakly assigned.

**Typicality formula** (from Ferrara et al., 2025):

```
Typicality(u) = product of (alpha_f * f(u)) for each feature f

where alpha_f = +1 if feature is High in the archetype
      alpha_f = -1 if feature is Low in the archetype
```

This means: for High features, higher raw values increase typicality; for Low features, lower raw values increase typicality.

```python
def compute_typicality(users):
    """Compute typicality score for each user within their archetype."""
    archetype_alphas = {
        'HHH': {'score': 1, 'sentiment': 1, 'toxicity': 1},
        'HHL': {'score': 1, 'sentiment': 1, 'toxicity': -1},
        'HLH': {'score': 1, 'sentiment': -1, 'toxicity': 1},
        'HLL': {'score': 1, 'sentiment': -1, 'toxicity': -1},
        'LHH': {'score': -1, 'sentiment': 1, 'toxicity': 1},
        'LHL': {'score': -1, 'sentiment': 1, 'toxicity': -1},
        'LLH': {'score': -1, 'sentiment': -1, 'toxicity': 1},
        'LLL': {'score': -1, 'sentiment': -1, 'toxicity': -1},
    }

    typicality = []
    for idx, row in users.iterrows():
        arch = row['archetype']
        alphas = archetype_alphas[arch]
        # Product of alpha_f * f(u)
        # Use small epsilon to avoid zero products
        eps = 1e-6
        score_val = max(row['norm_score'], eps)
        sent_val = max(row['norm_sentiment'], eps)
        tox_val = max(row['norm_toxicity'], eps)

        typ = (score_val ** alphas['score']) * \
              (sent_val ** alphas['sentiment']) * \
              (tox_val ** alphas['toxicity'])
        typicality.append(typ)

    users['typicality'] = typicality
    return users
```

**Interpreting typicality:** Users with the highest typicality in each archetype are the most "pure" exemplars. Users with low typicality sit near decision boundaries and may shift archetypes with small changes in behavior or threshold.

### Step 8: Analyze Archetype Distributions and Validate

**Distribution analysis:**

```python
def analyze_archetypes(users):
    """Compute archetype-level statistics."""
    summary = users.groupby('archetype').agg(
        count=('norm_score', 'size'),
        mean_score=('norm_score', 'mean'),
        mean_sentiment=('norm_sentiment', 'mean'),
        mean_toxicity=('norm_toxicity', 'mean'),
        mean_typicality=('typicality', 'mean'),
        median_typicality=('typicality', 'median'),
    ).round(3)

    summary['pct_of_total'] = (summary['count'] / summary['count'].sum() * 100).round(1)
    return summary
```

**Validation checks:**

| Check | Expected | If Violated |
|-------|----------|-------------|
| All 8 archetypes populated | At least 1 user per archetype | Some behavioral patterns absent; document which and why |
| No single archetype > 50% | Balanced distribution | Threshold may need adjustment; check for axis skew |
| H-axes have higher mean raw values than L-axes | By definition | Threshold or normalization error; recheck Step 5 |
| Typicality is not uniformly low | Median typicality > 0.1 per archetype | Users are clustered near thresholds; consider widening the "uncertain" zone |

### Step 9: Write Report

Write all findings to `docs/analysis/14-mdpi-hypernetwork-archetype.md`.

## Report Output Template

The final report MUST be written to `docs/analysis/14-mdpi-hypernetwork-archetype.md` with this structure:

```markdown
# MDPI Social Hypernetwork Archetype Classification

## Methodology

### Reference Framework
Based on Ferrara et al. (2025), "Characterizing User Archetypes and Discussions on
Social Hypernetworks" (MDPI Big Data and Cognitive Computing, 9(9), 236).

### Axes
| Axis | Source Metric | Scorer/Method | Normalization |
|------|-------------|---------------|---------------|
| Score | [metric name] | [computation method] | [normalization method] |
| Sentiment | [text field] | [VADER / other] | [shift from [-1,1] to [0,1] / other] |
| Toxicity | [text field] | [Detoxify / Perspective API / other] | [method] |

### Thresholds
| Axis | Threshold Value | Method | % High | % Low | Rationale |
|------|----------------|--------|--------|-------|-----------|
| Score | [value] | [fixed/median/domain] | [X%] | [Y%] | [why this method] |
| Sentiment | [value] | [fixed/median/domain] | [X%] | [Y%] | [why this method] |
| Toxicity | [value] | [fixed/median/domain] | [X%] | [Y%] | [why this method] |

### Corpus
- Total users classified: [N]
- Content items analyzed: [N posts + N comments]
- Date range: [if temporal data available]
- Platform: [platform name]

## Archetype Distribution

| Archetype | Count | % of Total | Mean Score | Mean Sentiment | Mean Toxicity | Mean Typicality |
|-----------|-------|-----------|------------|----------------|---------------|-----------------|
| HHH | ... | ... | ... | ... | ... | ... |
| HHL | ... | ... | ... | ... | ... | ... |
| HLH | ... | ... | ... | ... | ... | ... |
| HLL | ... | ... | ... | ... | ... | ... |
| LHH | ... | ... | ... | ... | ... | ... |
| LHL | ... | ... | ... | ... | ... | ... |
| LLH | ... | ... | ... | ... | ... | ... |
| LLL | ... | ... | ... | ... | ... | ... |

## Archetype Behavioral Profiles

### [For each populated archetype:]
- **Label:** [e.g., HHL]
- **Population:** [N users, X% of total]
- **Behavioral signature:** [Description from data]
- **Mean axis values:** Score=[X], Sentiment=[X], Toxicity=[X]
- **Typicality range:** [min - max], median=[X]
- **Emotional valence constraints:** [What style replication should preserve]
- **Most typical exemplar:** [User ID or anonymized label, typicality score]

## Threshold Sensitivity

[What happens when thresholds shift +/- 0.05 on each axis]
[How many users change archetype under small threshold perturbations]
[Identification of "boundary users" who are near thresholds on multiple axes]

## Limitations and Caveats
- Archetypes are behavioral patterns, NOT personality types or stable traits
- Classification is threshold-dependent; small changes can reassign boundary users
- Toxicity scores reflect classifier training data norms, not community norms
- [Corpus-specific limitations]
- [Missing axis limitations if applicable]
- Archetype distribution is specific to this corpus and time period; do not generalize

## References
- Ferrara et al. (2025). Characterizing User Archetypes and Discussions on Social
  Hypernetworks. Big Data and Cognitive Computing, 9(9), 236. https://doi.org/10.3390/bdcc9090236
- [Toxicity classifier reference]
- [Sentiment scorer reference]
```

## Good Patterns

- **Normalize all axes to [0, 1] before thresholding.** Raw scores on different scales produce meaningless splits. Normalization ensures the threshold has the same meaning on each axis.
- **Use established toxicity classifiers (Detoxify, Perspective API) with documented model versions.** Custom or ad-hoc toxicity scoring is not reproducible.
- **Document threshold rationale for every axis.** The choice between fixed 0.5, median split, and domain-informed thresholds changes the archetype distribution. Make the reasoning explicit.
- **Treat toxicity and sentiment as independent axes.** A comment can be positive-sentiment and high-toxicity ("Hell yeah!") or negative-sentiment and low-toxicity ("I respectfully disagree"). Conflating them collapses the dimensionality.
- **Report typicality alongside archetype labels.** A user labeled HHL with typicality 0.95 is a confident classification; one with typicality 0.02 is barely over the threshold on one axis.
- **State that archetypes describe behavior in the observed period.** Users may shift archetypes over time; the label is a snapshot, not an identity.
- **Auto-switch to median when fixed thresholds produce extreme imbalance (>80% on one side).** An 85/15 split means the threshold is not discriminating meaningfully.

## Anti-Patterns

| Anti-Pattern | Why It Fails | Instead |
|--------------|-------------|---------|
| Arbitrary High/Low cutoffs without justification | Reviewers cannot evaluate or reproduce the analysis; different thresholds produce different archetypes | Document threshold method, value, rationale, and H/L distribution per axis |
| Using raw scores without normalization | Score of 500 + sentiment of 0.3 + toxicity of 0.1 = score-dominated classification | Normalize all axes to [0, 1] before threshold comparison |
| Conflating sentiment with toxicity | Treats them as one dimension, losing the distinction between "negative but civil" (HLL) and "positive but aggressive" (LHH) | Always score and threshold them independently; verify with the 2x2 examples in Step 4 |
| Treating archetypes as personality types | Implies stability and identity; used to label people rather than describe behavior | Always state "behavioral pattern in [time period]" not "user type" |
| Applying a single toxicity threshold across different community norms | Gaming communities, NSFW communities, and professional forums have vastly different baseline toxicity | Use corpus-median splitting or document the community-norm discrepancy; never silently apply a single standard |
| Classifying with unnormalized Perspective API scores as severity | Perspective scores are probability, not severity; 0.7 means "70% likely toxic" not "moderately toxic" | Use scores as probability estimates; threshold based on probability, not assumed severity |
| Reporting archetypes without typicality scores | Gives false confidence in boundary cases | Always report typicality; flag users with typicality < 10th percentile as uncertain |
| Comparing archetype distributions across platforms without recalibrating | Different platforms have different engagement dynamics, sentiment baselines, and toxicity norms | Recalibrate thresholds per platform/community; compare distribution shapes, not absolute labels |

## Boundaries

**This skill SHOULD:**

- Classify users on three independent axes (Score, Sentiment, Toxicity)
- Assign one of eight archetype labels (HHH through LLL) per user
- Normalize all axes to [0, 1] before thresholding
- Document thresholds and their rationale for every axis
- Compute typicality scores to measure classification confidence
- Describe behavioral implications of each populated archetype
- Report archetype distributions with population counts and percentages
- Identify boundary users near thresholds
- Write findings to `docs/analysis/14-mdpi-hypernetwork-archetype.md`

**This skill should NOT:**

- Treat archetypes as fixed personality traits or stable identities
- Use classification for punitive purposes (banning, demoting, or penalizing users based on archetype)
- Assume archetypes are stable over time (they are period-specific behavioral snapshots)
- Conflate the classification with psychological diagnosis or personality assessment
- Apply uniform thresholds across different communities without validating the distributional fit
- Make causal claims about why users exhibit a particular archetype pattern
- Compare absolute archetype labels across different platforms without recalibrating
- Classify users with fewer than 5 content items (insufficient behavioral sample)

## Insufficient Data Handling

### When One Axis Lacks Data

| Missing Axis | Impact | Strategy |
|-------------|--------|----------|
| **No toxicity scores** | Cannot distinguish civil from toxic users. HHH/HHL collapse, HLH/HLL collapse, etc. | Fall back to two-axis classification (Score x Sentiment = 4 archetypes: HH, HL, LH, LL). Document that toxicity was unavailable and what archetypes could not be differentiated. |
| **No sentiment scores** | Cannot distinguish positive from negative users. HHH/HLH collapse, etc. | Fall back to two-axis (Score x Toxicity = 4 archetypes). Less common -- if you have text, you can usually score sentiment. |
| **No score/engagement data** | Cannot distinguish high-visibility from low-visibility users. | Fall back to two-axis (Sentiment x Toxicity = 4 archetypes). Common in data exports without engagement metrics. |

### Two-Axis Fallback Classification

When only two axes are available, classify on a 2x2 grid:

**Score x Sentiment (no toxicity):**

| | High Sentiment | Low Sentiment |
|---|---|---|
| **High Score** | HS: Visible, positive | HL: Visible, critical |
| **Low Score** | LS: Quiet, positive | LL: Quiet, critical |

**Score x Toxicity (no sentiment):**

| | High Toxicity | Low Toxicity |
|---|---|---|
| **High Score** | HT: Visible, aggressive | HC: Visible, civil |
| **Low Score** | LT: Quiet, aggressive | LC: Quiet, civil |

**Sentiment x Toxicity (no score):**

| | High Toxicity | Low Toxicity |
|---|---|---|
| **High Sentiment** | PT: Positive, aggressive | PC: Positive, civil |
| **Low Sentiment** | NT: Negative, aggressive | NC: Negative, civil |

Document which two-axis model was used and why the third axis was unavailable.

### When Corpus Is Too Small for Reliable Scoring

| Condition | Action |
|-----------|--------|
| **< 30 users** | Do NOT assign archetypes. Report individual axis scores per user in a table. State that the corpus is below the minimum for distributional classification. |
| **30-99 users with sparse text** | Classify but flag all archetypes with < 5 members as "insufficient evidence." Report typicality distributions to show confidence levels. |
| **Users with < 5 content items** | Exclude from classification. Report them separately as "insufficient behavioral sample." Include count of excluded users. |
| **Single content item per user** | That content item IS the user's score/sentiment/toxicity. No mean is meaningful. Exclude or flag as single-observation classification. |

### When Scores Cluster Near Thresholds

If more than 40% of users on any axis fall within +/- 0.05 of the threshold, that axis has low discriminative power.

**Strategies:**

1. **Report the clustering explicitly.** The threshold is splitting a homogeneous group arbitrarily.
2. **Widen the "uncertain" zone.** Users within +/- 0.05 of the threshold on ANY axis get flagged as "boundary" and their archetype label carries a confidence caveat.
3. **Use a three-tier classification for the clustered axis** (High / Uncertain / Low) and report the expanded set of archetypes separately.
4. **Consider whether the axis provides meaningful discrimination.** If 90% of users are in a narrow band on toxicity (e.g., all very low), that axis may not differentiate behavior in this community. Document this and consider the two-axis fallback.

```python
def identify_boundary_users(users, thresholds, margin=0.05):
    """Flag users near decision boundaries on any axis."""
    boundary_flags = pd.DataFrame(index=users.index)
    for axis in ['score', 'sentiment', 'toxicity']:
        col = f'norm_{axis}'
        thresh = thresholds[axis]['threshold']
        boundary_flags[f'{axis}_boundary'] = (
            (users[col] >= thresh - margin) & (users[col] <= thresh + margin)
        )
    boundary_flags['any_boundary'] = boundary_flags.any(axis=1)
    boundary_flags['n_boundary_axes'] = boundary_flags[
        [c for c in boundary_flags.columns if c != 'any_boundary']
    ].sum(axis=1)

    pct_boundary = boundary_flags['any_boundary'].mean() * 100
    print(f"Boundary users (within +/-{margin} of threshold on any axis): "
          f"{boundary_flags['any_boundary'].sum()} ({pct_boundary:.1f}%)")
    return boundary_flags
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Conflating toxicity with negative sentiment | Score them independently. A respectful disagreement is negative-sentiment, low-toxicity. A profane compliment is positive-sentiment, high-toxicity. |
| Using a single threshold for all communities | Each community has different baselines. Use median splitting or document why a fixed threshold is appropriate. |
| Reporting archetypes without typicality | Typicality reveals confidence. A user at HHL with typicality 0.01 is barely distinguishable from HLL. |
| Classifying users with too few posts | Fewer than 5 content items produces noisy axis scores. Exclude or flag these users. |
| Treating archetype labels as permanent | Behavior changes over time. Always state the classification period. |
| Not checking archetype population balance | If one archetype has 60% of users, the threshold is not discriminating. Adjust or document. |
| Using Perspective API scores as severity | Perspective outputs probability of toxicity, not severity. 0.9 means "very likely toxic," not "severely toxic." |
| Skipping normalization because "all axes are [0,1]" | Even if raw ranges are [0,1], the distributions may cluster differently. Normalize within the observed corpus range. |
| Drawing causal conclusions from archetypes | Archetypes describe patterns, not causes. "HLH users ARE antagonistic" is different from "HLH users EXHIBIT antagonistic patterns in this period." |

## References

- Ferrara, E., Ferrara, A., & Ferrara, M. (2025). [Characterizing User Archetypes and Discussions on Social Hypernetworks](https://www.mdpi.com/2504-2289/9/9/236). Big Data and Cognitive Computing, 9(9), 236.
- Ferrara et al. (2024). [Characterizing User Archetypes and Discussions on Scored.co](https://arxiv.org/abs/2407.21753). arXiv:2407.21753 (preprint of the above).
- Hutto, C.J. & Gilbert, E.E. (2014). [VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text](https://ojs.aaai.org/index.php/ICWSM/article/download/14550/14399/18068). ICWSM.
- Hanu, L. & Unitary team (2020). [Detoxify: Toxic Comment Classification](https://github.com/unitaryai/detoxify). GitHub.
- Jigsaw / Google (2017). [Perspective API](https://perspectiveapi.com/). perspectiveapi.com.
- Gervais, B.T., Dye, C., & Chin, A. (2025). [Incivility or Invalidity? Evaluating Perspective API Scores as a Measure of Political Incivility](https://journals.sagepub.com/doi/10.1177/1532673X241309627). Political Research Quarterly.
