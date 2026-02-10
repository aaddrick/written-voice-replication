# Analysis Guide: Structured Data Export to Persona Synthesis

A guide for applying analytical techniques to a structured data export (e.g., Reddit GDPR export) to produce a **Persona Synthesis and Style Replication** — an actionable communication profile that can reproduce a user's voice.

---

## Phase 1: Data Preparation

### 1. CSV Metadata Forensic Reconstruction

Cross-reference metadata headers across the core export files (`posts.csv`, `comments.csv`, `account.csv`, `saved.csv`, `votes.csv`) to establish baseline metrics:

- **Digital persona lifespan**: delta between `registration_date` and the most recent `timestamp`.
- **Creator vs. participant ratio**: posts-to-comments ratio indicating content role.

These baselines inform how subsequent analyses should be scoped and weighted.

### 2. Tiered Computational Processing Pipeline

Process the raw export in two stages:

- **Stage 1 — CLI tools**: Clean data, parse metadata, and extract URLs using tools like Exiftool and Minet.
- **Stage 2 — Python pipelines**: Feed cleaned data into analytical frameworks such as `reddit-post-collector-analyzer`, integrating LLMs with traditional sentiment analysis.

### 3. Automated Orchestration with Checkpoints

Use a pipeline manager (e.g., `reddit_orchestrator.py`) to coordinate collection, cleaning, sentiment analysis, and visualization. Enable:

- **Checkpoint/resume**: So interrupted analyses can resume across API rate limits and large archives.
- **Activity-based depth adjustment**: Scale analysis depth based on subreddit size (high-activity communities vs. niche ones with <10,000 members).

---

## Phase 2: Content and Interest Analysis

### 4. Taxonomic Interest Classification

Map the user's subreddit distribution against Reddit's hierarchical interest taxonomy (Interest Group > Subgroup). Measure **interest orthogonality** — how diverse or concentrated the user's activity is — to determine whether the profile is polymathic or specialist. This classification feeds into the final archetype assignment.

### 5. Non-negative Matrix Factorization (NMF) for Topic Modeling

Apply NMF to the full comment/post corpus to discover 8–10 **latent themes** that cut across explicit subreddit labels. This reveals connections between seemingly unrelated interests that simple subreddit categorization would miss, and provides a deeper map of the user's intellectual territory.

### 6. LLM-Based Relevance Scoring

Use a Large Language Model (e.g., Llama 3, Mistral via Ollama) to assign a 0–100 **relevance score** to individual posts. This evaluates the substance of contributions — distinguishing detailed explanations from low-effort reactions — and identifies **Authority Peaks**: moments where the user served as a primary knowledge source.

---

## Phase 3: Sentiment and Engagement Analysis

### 7. VADER Sentiment Analysis

Apply the VADER (Valence Aware Dictionary and sEntiment Reasoner) framework at three tiers:

| Tier | Source | Purpose |
|------|--------|---------|
| Title | Post title | First-impression tone |
| Body | Post/comment content | Detailed emotional expression |
| Reactions | Community comments | Discursive alignment or divergence |

**Compound score formula:**

$$S_{compound} = \frac{\sum V_i}{\sqrt{(\sum V_i)^2 + \alpha}}$$

Where $V_i$ is per-word valence adjusted for intensifiers and contrastive conjunctions, and $\alpha$ is a normalization constant. Produces a score from -1.0 to +1.0.

Apply longitudinally to identify patterns such as sentiment stabilization or volatility peaks tied to external events.

### 8. Weighted Engagement Scoring

Calculate a composite influence metric as a weighted sum:

$$E = \sum (w_i \cdot x_i)$$

| Metric | Weight | Rationale |
|--------|--------|-----------|
| Reddit Score | 0.30 | Community consensus and visibility |
| Upvote Ratio | 0.25 | Controversiality vs. universality |
| Comment Volume | 0.25 | Discursive impact and topic stickiness |
| Sentiment Quality | 0.15 | Constructive engagement vs. toxic volume |
| Temporal Recency | 0.05 | Relevance decay in fast-moving contexts |

Use the resulting scores to isolate the user's **high-value discussions** — the posts that best represent their substantive voice.

### 9. Supplementary Engagement Analyses

Apply these additional lenses to refine the engagement picture:

- **Sentiment-Engagement Correlation**: Determine whether the user's highest-scoring posts are also their most emotionally charged, distinguishing authentic voice from crowd-pleasing.
- **Authority and Influence Mapping**: Measure **Comment Depth** — threads where discussion continues long after the original poster has left — to identify a "discursive catalyst" role.
- **Privacy Audit**: Review `saved.csv` and `votes.csv` for non-public data points that may inform the profile but carry privacy risk.

### 10. Network and Social Graph Analysis

Map the user's interaction network from `comments.csv` reply chains and `parent_id` relationships. Identify:

- **Frequent interlocutors**: Users the subject repeatedly engages with, and whether those interactions are collaborative or adversarial.
- **Audience-dependent voice shifts**: Whether tone, vocabulary, or argument style changes when replying to newcomers vs. established peers vs. antagonists.
- **Reciprocity patterns**: Ratio of initiating threads vs. responding, and whether the user engages with those who reply to them.

This analysis determines whether the style replication needs audience-awareness — adjusting voice based on the perceived interlocutor — or whether a single stable voice suffices.

---

## Phase 4: Temporal and Behavioral Analysis

### 11. Longitudinal Growth Curve Modeling

Apply growth curve models to temporal metadata to track the user's evolution through stages of **Digital Maturity**:

Lurker (observer) → Participant → Community leader/moderator

Identify where the user currently sits and how their engagement style has shifted over time.

### 12. Temporal and Circadian Pattern Analysis

Aggregate timestamps into hourly/daily/weekly/seasonal bins to reconstruct an activity profile. Look for:

| Pattern | Indicator | Inference |
|---------|-----------|-----------|
| Daily regularity | Consistent posting in a narrow time window | Primary engagement period |
| Weekly spikes | Weekend vs. weekday variation | Work-life separation |
| Seasonal peaks | Multi-week activity surges | Life events, industry events |
| Intermittent bursts | Short high-intensity periods | Project-based or reactive engagement |

### 13. Taxonomic Shift Detection

Use longitudinal modeling to identify when the user migrates from one interest subgroup to another. These "Subreddit Migrations" are often the clearest data indicator of a major life transition or professional pivot, and signal which phase of the user's history best represents their current voice.

---

## Phase 5: Psycholinguistic Profiling

### 14. MDPI Social Hypernetwork Archetype Classification

Classify the user along three axes — **Score**, **Sentiment**, and **Toxicity** (each rated High or Low) — to assign a behavioral archetype. The eight possible combinations (e.g., HHL, HLL, LHL) each describe a distinct engagement pattern. This archetype directly determines the emotional valence constraints for the final style specification.

### 15. Big Five (OCEAN) Personality Profiling

Infer personality traits from linguistic markers in the user's writing:

| Trait | Linguistic Indicators to Measure |
|-------|----------------------------------|
| **Openness** | Density of intellectual, cultural, and complex vocabulary |
| **Conscientiousness** | Frequency of achievement-oriented word choices; formality and structure |
| **Neuroticism** (inverted as Emotional Stability) | Density of negative-affect vocabulary |
| **Extraversion** | Frequency of social and positive emotion terms vs. task-oriented content |
| **Agreeableness** | Tone warmth and reciprocity patterns |

Each trait maps to a writing constraint in the final synthesis.

### 16. LIWC (Linguistic Inquiry and Word Count) Psycholinguistic Analysis

Categorize the user's vocabulary into psychological dimensions: cognitive processes, social drives, biological needs, and emotional states. Determine the dominant dimensions to establish which linguistic registers the style replication should prioritize.

### 17. Communication Accommodation Theory (CAT) and Linguistic Style Matching

Measure how the user **converges** toward community norms by comparing their function-word usage against community baselines via **Linguistic Style Matching (LSM)**. Identify which communities the user accommodates most strongly — these represent the professional or social standards the replication should target.

### 18. Stylometric Fingerprinting

Extract the user's stable pattern of **function word usage** and **sentence structure** across subreddits and time periods. This fingerprint defines the syntactic constraints for the style replication — the structural habits that make the user's writing identifiable regardless of topic.

### 19. Readability and Lexical Diversity Metrics

Compute quantitative complexity targets from the user's corpus:

- **Readability**: Flesch-Kincaid grade level, Coleman-Liau index, and average sentence length establish the complexity ceiling and floor for replicated output.
- **Lexical diversity**: Type-token ratio (TTR) and hapax legomena frequency measure how varied or repetitive the user's vocabulary is.

These metrics translate directly into measurable LLM prompt constraints (e.g., "target a Flesch-Kincaid grade level of 12–14" or "maintain a TTR above 0.6").

### 20. Rhetorical and Discourse Structure Analysis

Examine how the user constructs arguments beyond the word level:

- **Argument ordering**: Does the user lead with evidence then conclude, or state a position then defend it?
- **Rhetorical devices**: Frequency of analogies, hedging ("I think," "arguably"), rhetorical questions, concessions ("granted," "to be fair"), and qualifications.
- **Paragraph and post structure**: Typical length, use of lists vs. prose, whether they include a summary or call to action.

These structural habits are often more recognizable than vocabulary and are critical for authentic replication.

### 21. Register Variation and Code-Switching Analysis

Measure how much the user's voice varies across different subreddits and contexts. Compare vocabulary, formality, sentence length, and sentiment distributions between the user's most active communities. Classify the user as:

- **Stable register**: Minimal variation — a single voice applies across contexts.
- **Context-dependent register**: Significant shifts — the replication needs conditional rules (e.g., "in technical subreddits use X style, in casual subreddits use Y").

This determines whether the final subagent instruction produces one voice or a context-aware set of voices.

### 22. Speech Act and Pragmatic Analysis

Categorize the user's posts and comments by their communicative function:

| Speech Act | Indicators |
|------------|-----------|
| **Asserting** | Declarative statements, factual claims |
| **Advising** | Imperative constructions, "you should," recommendation framing |
| **Explaining** | Causal connectors ("because," "this means"), step-by-step structure |
| **Questioning** | Interrogatives, requests for clarification |
| **Challenging** | Counter-arguments, "but," "however," refutation patterns |
| **Agreeing/Supporting** | Affirmations, elaborations on others' points |

Determine the user's dominant speech acts and their relative proportions. Two users with identical sentiment and vocabulary profiles can have entirely different pragmatic signatures — one primarily explains while the other primarily challenges — making this a major differentiator for voice authenticity.

---

## Phase 6: Persona Archetype Classification

### 23. Archetype Assignment

Synthesize the outputs of phases 2–5 (taxonomy, sentiment, engagement, temporal patterns, psycholinguistic profile) to assign a **Persona Archetype**. Reference archetypes include:

- **Subject Matter Expert (SME)**: High scores in niche subreddits, instructional tone, high upvote ratios.
- **Lurker-turned-Leader**: Sparse early comments evolving into high-karma posts or moderator status.
- **Community Gatekeeper**: Active in meta subreddits, significant downvote activity, neutral-to-negative sentiment.
- **Emotional Support Seeker**: Concentrated in relationships/health subreddits, high reciprocity, sentiment valleys during distress.
- **Digital Nomad/Generalist**: No single subgroup dominating activity, platform used as a news aggregator.

The assigned archetype provides the high-level persona label; the psycholinguistic profile provides the granular style parameters.

---

## Phase 7: Persona Synthesis and Style Replication

### 24. Building the Style Specification

Map each analysis output to a concrete writing constraint:

| Analysis Output | Derived Constraint |
|-----------------|-------------------|
| MDPI Archetype (Score/Sentiment/Toxicity) | Emotional valence boundaries for the output tone |
| Big Five — Openness | Vocabulary complexity level |
| Big Five — Conscientiousness | Formality and structural rigor |
| LIWC dominant dimensions | Which linguistic registers to prioritize (cognitive, social, affective, etc.) |
| Stylometric Fingerprint | Function-word patterns and sentence structure to maintain |
| Readability / Lexical Diversity | Measurable complexity targets (grade level, TTR) |
| CAT / LSM target communities | Professional or social standards the output should converge toward |
| Rhetorical Structure | Argument ordering, hedging frequency, structural habits |
| Register Variation | Whether to produce one voice or context-dependent voices |
| Speech Act Distribution | Proportions of explaining, advising, challenging, etc. |
| Social Graph / Audience Patterns | Whether voice requires audience-awareness adjustments |
| Persona Archetype | Overall voice and role framing |

### 25. Operationalizing as a Subagent Instruction

Translate the style specification into a prompt instruction for an LLM subagent. The instruction should define:

- **Informational density**: Noun-heavy vs. conversational, based on LIWC and archetype.
- **Emotional valence control**: Enforces the MDPI archetype boundaries — specifying which affective registers to use or avoid.
- **Evidence framing**: Degree to which claims require supporting evidence, derived from Conscientiousness and archetype.
- **Syntactic stability**: Maintains the stylometric fingerprint across the full output.
- **Complexity targets**: Enforces the readability grade level and lexical diversity range measured from the corpus.
- **Rhetorical structure**: Replicates the user's argument ordering, hedging patterns, and post structure.
- **Pragmatic distribution**: Matches the user's ratio of speech acts — how much the output explains vs. advises vs. challenges vs. asserts.
- **Register rules**: If the user is context-dependent, includes conditional style rules keyed to the target community or audience.
- **Community convergence**: Uses CAT as a generative principle — the subagent converges toward the professional standards of the user's most engaged communities rather than producing a generic tone.

The goal is an instruction that reproduces the user's archival voice as identified through the preceding analysis, not an assumed or generic style.
