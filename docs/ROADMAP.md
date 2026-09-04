# AI Writing Intelligence Platform Roadmap
## Dutch + English First | Detector First | Humanizer Second

Version: 1.0
Primary languages: Dutch (NL) and English (EN)

---

# 1. Product Vision

Build a high-quality writing intelligence platform with four core systems:

1. AI Detector
2. Humanizer / Natural Writing Engine
3. Writing & Style Analyzer
4. Evaluation / Benchmark Engine

The product should not promise that text can be made "undetectable."
Instead, it should improve naturalness, preserve meaning, adapt to the user's style,
and give calibrated estimates of likely AI involvement.

Core positioning:

"Understand how text was likely created, then improve it without losing the author's meaning or voice."

---

# 2. Development Order

## Phase A — Detector First
Build the detector and benchmarking infrastructure before the humanizer.

Why:
- It creates the measurement system for everything else.
- It helps compare human, AI, mixed, translated, and AI-edited text.
- It gives you a reusable evaluation layer for Dutch and English.

Order:

1. Dutch + English data collection
2. HumanBench-NL/EN benchmark
3. Detector V1
4. Sentence-level detector
5. Mixed-authorship detector
6. Detector calibration
7. Humanizer V1
8. Style DNA
9. Meaning-preservation system
10. Humanizer modes
11. Multilingual expansion
12. Enterprise/API integrations

---

# 3. HumanBench-NL/EN

Create a benchmark dataset before training the production detector.

## Languages

### Dutch
- Netherlands Dutch
- Belgian/Flemish Dutch where possible
- Formal Dutch
- Informal Dutch
- Student writing
- Business writing
- Social writing
- Marketing copy
- News-style writing
- Technical writing

### English
- US English
- UK English
- International English
- Formal English
- Informal English
- Student writing
- Business writing
- Social writing
- Marketing copy
- News-style writing
- Technical writing

## Authorship Classes

Do not use only:
- Human
- AI

Use a spectrum:

1. Fully human
2. Human + spelling correction
3. Human + grammar correction
4. Human + AI suggestions
5. Human heavily edited by AI
6. Mixed human/AI
7. AI draft + light human editing
8. AI draft + heavy human editing
9. Fully AI
10. Uncertain

## Length Buckets

- 20–50 words
- 50–100 words
- 100–250 words
- 250–500 words
- 500–1,000 words
- 1,000+ words

## Domain Buckets

- School essays
- University writing
- Business emails
- Customer support
- Reports
- Blog posts
- Journalism
- Marketing
- Product descriptions
- Social media
- Chat / messages
- Technical documentation
- Creative writing

---

# 4. Detector V1

## Detector Architecture

TEXT
 |
 +--> Language detection
 |
 +--> Neural text classifier
 |
 +--> Stylometric feature model
 |
 +--> Statistical / probability-based features
 |
 +--> Sentence variation analysis
 |
 +--> Paragraph consistency analysis
 |
 +--> Domain classifier
 |
 +--> Calibration layer
 |
 +--> Final authorship estimate

## Output Classes

- Likely Human
- Mostly Human
- Mixed / AI-assisted
- Mostly AI
- Likely AI
- Uncertain

## Output Example

Language: Dutch
Likely Human: 62%
Mixed / AI-assisted: 28%
Likely AI: 10%
Confidence: Medium

Important:
Probabilities must be calibrated.
Never present the result as absolute proof.

---

# 5. Sentence-Level Detection

Analyze text in overlapping chunks.

Example:

Paragraph 1: likely human
Paragraph 2: uncertain
Paragraph 3: AI-like
Paragraph 4: mixed
Paragraph 5: likely human

Add a visual heatmap in the UI.

Possible signals:
- sentence-length regularity
- syntax repetition
- paragraph symmetry
- lexical diversity
- token predictability
- unusual transition density
- phrase repetition
- excessive structural consistency
- semantic redundancy
- burstiness
- punctuation patterns
- discourse markers

Do not create simplistic rules such as:
"uses word X = AI"

---

# 6. Dutch-Specific Detector Work

Dutch needs its own evaluation and feature testing.

Test:
- common Dutch sentence structures
- compound words
- separable verbs
- modal particles
- informal contractions
- Belgian/Flemish vocabulary
- formal government/business language
- translated English-to-Dutch text
- AI-written Dutch generated directly
- AI-written English translated to Dutch
- human Dutch grammar-corrected by AI

Important hard negatives:
- non-native Dutch writers
- dyslexic writers
- highly formal Dutch
- legal Dutch
- academic Dutch
- simplified Dutch
- heavily corrected Dutch

---

# 7. English-Specific Detector Work

Test:
- US vs UK spelling
- international/non-native English
- academic English
- business English
- technical writing
- polished marketing copy
- grammar-corrected human writing
- translated writing
- AI-polished human writing
- highly structured human essays

Hard negatives:
- ESL writers
- extremely formal writers
- journalists
- legal writers
- technical documentation
- template-based corporate writing

---

# 8. Detector Metrics

Primary metrics:

- TPR at 1% false-positive rate
- TPR at 5% false-positive rate
- ROC-AUC
- Precision
- Recall
- F1
- Calibration error
- Domain robustness
- Cross-model robustness
- Dutch score
- English score
- Mixed-authorship score

Never optimize only for generic "accuracy."

Main rule:
A detector that falsely labels real human writing is dangerous.

---

# 9. Humanizer V1

The humanizer starts after the detector benchmark is working.

Goal:
Improve naturalness while preserving meaning, facts, intent, and user voice.

Pipeline:

INPUT
 |
 +--> Language detection
 |
 +--> Intent extraction
 |
 +--> Meaning/fact anchors
 |
 +--> Tone analysis
 |
 +--> Style analysis
 |
 +--> Rewrite planner
 |
 +--> Candidate generation
 |
 +--> Naturalness critic
 |
 +--> Meaning-preservation critic
 |
 +--> Grammar check
 |
 +--> Final rewrite

---

# 10. Humanizing Methods

The humanizer should have many independent techniques.

## A. Sentence Variation

Adjust:
- sentence length
- sentence openings
- clause structure
- rhythm
- punctuation
- short vs long sentence balance

Avoid:
- every sentence having the same length
- repeated "This means..."
- repeated "Furthermore..."
- repeated paragraph patterns

---

## B. Natural Transitions

Replace overly mechanical transitions.

Possible styles:
- conversational
- academic
- professional
- subtle
- direct
- narrative

Dutch examples:
- daarnaast
- toch
- daarom
- tegelijk
- juist
- in de praktijk
- bovendien
- uiteindelijk
- aan de andere kant

English examples:
- still
- that said
- in practice
- meanwhile
- because of that
- on the other hand
- more importantly

The system should not overuse any transition.

---

## C. Vocabulary Naturalization

Detect:
- unnecessarily formal words
- repetitive vocabulary
- unnatural synonyms
- overly generic wording
- corporate filler
- machine-like phrasing

Controls:
- simple
- natural
- professional
- advanced
- academic
- casual

---

## D. Contraction Control

English:
- do not -> don't
- cannot -> can't
- it is -> it's

Dutch:
Use natural informal constructions only where appropriate.

Control:
- none
- light
- normal
- conversational

---

## E. Personal Voice

Add or preserve:
- opinions
- preferences
- personal framing
- uncertainty
- emphasis
- characteristic expressions

Only when consistent with the user's intent.

Never invent personal experiences.

---

## F. Rhythm Humanization

Analyze:
- short/medium/long sentence sequence
- paragraph cadence
- pauses
- punctuation rhythm
- sentence complexity

Create more natural variation without making text sloppy.

---

## G. Paragraph Restructuring

Allow:
- split long paragraphs
- merge fragments
- move supporting details
- vary paragraph lengths
- change paragraph openings
- improve logical progression

---

## H. Redundancy Reduction

Remove:
- repeated conclusions
- repeated topic sentences
- unnecessary summaries
- restating the same idea in multiple ways

---

## I. Specificity Improvement

Generic:
"The solution provides many benefits."

Better:
"The tool cuts manual review by highlighting the sentences that need attention."

Do not invent facts.
If details are unknown, retain generality.

---

## J. Directness Adjustment

Modes:
- very direct
- direct
- balanced
- diplomatic
- soft

Useful for:
- emails
- business writing
- customer support
- feedback

---

## K. Tone Matching

Possible tones:
- casual
- friendly
- professional
- formal
- academic
- confident
- warm
- concise
- persuasive
- neutral
- enthusiastic
- serious
- technical
- humorous
- empathetic

---

## L. Imperfection Without Errors

Natural writing is not perfectly uniform.

Possible safe variation:
- occasional sentence fragments in informal writing
- conversational emphasis
- varied punctuation
- non-uniform paragraph sizes
- informal phrasing

Do NOT deliberately add:
- spelling mistakes
- fake grammar errors
- false facts
- random slang

---

## M. Register Matching

Dutch:
- jij/je
- u
- neutral professional

English:
- casual
- neutral
- formal

Keep register consistent.

---

## N. Locale Matching

Dutch:
- Netherlands
- Belgium/Flanders

English:
- US
- UK
- international

Handle:
- spelling
- vocabulary
- punctuation
- date formatting
- idioms

---

## O. Idiom Control

Use local idioms carefully.

Dutch example types:
- everyday expressions
- business expressions
- informal phrasing

English:
- US expressions
- UK expressions
- neutral international expressions

Never force idioms into every paragraph.

---

## P. Formality Shifting

Scale:
1 = very casual
2 = conversational
3 = neutral
4 = professional
5 = formal
6 = academic

---

## Q. Conciseness Control

Modes:
- shorten aggressively
- concise
- balanced
- detailed
- expanded

---

## R. Complexity Control

Modes:
- A2/simple
- B1
- B2
- C1
- academic/technical

Useful especially for Dutch and English learners.

---

## S. Audience Adaptation

Rewrite for:
- customer
- colleague
- manager
- student
- professor
- executive
- general public
- technical reader
- child/teen
- social-media audience

---

## T. Purpose Adaptation

Modes:
- explain
- persuade
- inform
- summarize
- sell
- request
- apologize
- complain
- teach
- entertain
- report

---

## U. Emotional Tone

Controls:
- neutral
- warm
- excited
- calm
- assertive
- empathetic
- urgent

Do not manipulate facts.

---

## V. Style Preservation

Preserve:
- favorite expressions
- sentence length tendencies
- punctuation style
- preferred vocabulary
- level of directness
- humor
- emoji use
- paragraph length

---

## W. User Style DNA

Ask users to provide writing samples.

Learn:
- average sentence length
- vocabulary level
- formality
- directness
- contractions
- punctuation
- emoji usage
- humor
- paragraph length
- sentence variation
- preferred transitions
- typical openings
- typical closings

Modes:
- Sound like me
- Sound like me but clearer
- Sound like me but more professional
- Sound like me but shorter
- Sound like me but warmer

---

## X. Multi-Pass Humanizing

Pass 1:
Meaning preservation

Pass 2:
Structure

Pass 3:
Style

Pass 4:
Naturalness

Pass 5:
Grammar and consistency

Pass 6:
Final meaning comparison

---

# 11. Specialized Humanizer Modes

## Dutch Modes
- Natuurlijk Nederlands
- Zakelijk Nederlands
- Informeel Nederlands
- Academisch Nederlands
- Studentenstijl
- Professionele e-mail
- Marketing
- Social media
- Klantenservice
- Vlaams
- Nederlands-Nederland

## English Modes
- Natural English
- Professional English
- Academic English
- Student writing
- Email
- Marketing
- Social media
- Customer support
- US English
- UK English
- International English

---

# 12. Meaning Preservation

Every rewrite should compare original and output.

Checks:
- named entities
- numbers
- dates
- percentages
- claims
- negations
- technical terms
- quotes
- citations
- causal relationships

Example warning:

Meaning preservation: 96%

Warning:
Original: "Revenue grew approximately 18%."
Rewrite: "Revenue grew more than 20%."

The system should reject or repair this rewrite.

---

# 13. Factuality Guard

Before returning a rewrite:

1. Extract claims
2. Compare claims before/after
3. Detect newly introduced facts
4. Detect missing facts
5. Detect changed numbers
6. Detect changed certainty
7. Detect changed attribution

Goal:
Natural writing without hallucinations.

---

# 14. Humanizer Quality Score

Score each rewrite on:

- Meaning preservation
- Naturalness
- Style match
- Grammar
- Readability
- Tone match
- Repetition
- Structural variety
- Locale correctness

Example:

Naturalness: 93
Meaning preservation: 99
Style match: 88
Grammar: 97
Readability: 92
Locale match: 100

---

# 15. A/B/C Candidate Generation

Generate multiple rewrite candidates:

A = safest / closest to original
B = most natural
C = strongest style adaptation

Let user select.

Store consented preference data:
- chosen candidate
- rejected candidates
- manual edits
- final accepted version

This becomes training data for a proprietary preference model.

---

# 16. Mixed-Language Handling

Support:
- Dutch with English business terms
- English text with Dutch phrases
- code-switching
- product names
- brand terms
- technical terms

Do not "correct" legitimate code-switching automatically.

---

# 17. Humanizer Safety Constraints

Do not optimize the system around:
- "100% undetectable"
- bypassing school integrity systems
- defeating moderation
- fabricating human authorship proof

Optimize around:
- better writing
- naturalness
- personalization
- meaning preservation
- transparency
- user control

---

# 18. UX Structure

Main navigation:

1. Detect
2. Humanize
3. Analyze
4. Compare
5. My Style
6. History
7. API

## Detect Screen

Input text

Output:
- language
- authorship estimate
- confidence
- sentence heatmap
- mixed-text estimate
- warnings
- explanation

## Humanize Screen

Input text

Controls:
- language
- locale
- tone
- formality
- sentence variation
- vocabulary
- conciseness
- audience
- purpose
- preserve wording
- use Style DNA

Output:
- Candidate A
- Candidate B
- Candidate C
- meaning score
- naturalness score

---

# 19. Technical Stack

Frontend:
- Next.js
- TypeScript
- Tailwind CSS

Backend:
- Python
- FastAPI

Database:
- PostgreSQL

Cache:
- Redis

ML:
- PyTorch
- Hugging Face Transformers

Experiment tracking:
- MLflow or Weights & Biases

Jobs:
- Celery or Temporal

Analytics:
- PostHog

Infrastructure:
- AWS, GCP, or Azure

---

# 20. Model Architecture

## Detector

Possible components:
- Dutch/English transformer classifier
- multilingual fallback classifier
- stylometric model
- statistical feature model
- sentence-level classifier
- domain classifier
- calibration model

Ensemble final score.

## Humanizer

Use a model router.

humanize(
    text,
    language,
    locale,
    tone,
    formality,
    audience,
    purpose,
    style_profile
)

Return:
- rewrites
- scores
- warnings

---

# 21. API Design

POST /detect

Input:
{
  "text": "...",
  "language": "auto"
}

Output:
{
  "language": "nl",
  "human_probability": 0.62,
  "mixed_probability": 0.28,
  "ai_probability": 0.10,
  "confidence": "medium",
  "segments": []
}

POST /humanize

Input:
{
  "text": "...",
  "language": "nl",
  "locale": "NL",
  "tone": "professional",
  "formality": 3,
  "style_profile_id": "..."
}

Output:
{
  "candidates": [],
  "meaning_preservation": [],
  "naturalness": []
}

POST /compare

POST /analyze

POST /style-profile

---

# 22. First MVP

## Detector MVP

Build first:

- Dutch detection
- English detection
- automatic language detection
- Human / Mixed / AI classes
- confidence level
- paragraph-level analysis
- basic sentence heatmap
- 5 major domains
- calibration dashboard

## Humanizer MVP

Then build:

- Dutch + English
- natural mode
- professional mode
- academic mode
- casual mode
- concise mode
- Style DNA
- tone control
- sentence variation
- vocabulary naturalization
- paragraph restructuring
- meaning-preservation score

---

# 23. 12-Month Roadmap

## Month 1
- Data pipeline
- NL/EN benchmark dataset
- annotation schema
- evaluation dashboard

## Month 2
- Detector baseline
- transformer classifier
- stylometric model

## Month 3
- ensemble detector
- calibration
- sentence-level analysis
- first private beta

## Month 4
- mixed-authorship model
- domain calibration
- Dutch/English robustness tests

## Month 5
- Humanizer V1
- meaning preservation
- naturalness scoring

## Month 6
- Style DNA
- multiple humanizer modes
- rewrite A/B/C

## Month 7
- user preference learning
- Dutch locale improvements
- English locale improvements

## Month 8
- Chrome extension
- Google Docs integration
- Microsoft Word integration

## Month 9
- public API
- team accounts
- organization controls

## Month 10
- detector V2
- unseen-model testing
- adversarial robustness
- multilingual experiments

## Month 11
- enterprise dashboard
- audit logs
- batch document analysis

## Month 12
- external benchmark publication
- third-party evaluation
- expand languages

---

# 24. Product Moat

The moat should be:

1. Dutch + English benchmark data
2. Human / Mixed / AI labeled data
3. High-quality hard negatives
4. Style DNA profiles
5. Rewrite preference data
6. Meaning-preservation evaluator
7. Continuously updated model benchmarks
8. Domain-specific calibration
9. User feedback loop
10. Transparent uncertainty

Do not make the base LLM your moat.

---

# 25. North-Star Product Goals

Detector:
"Reliable authorship estimation with very low false-positive rates."

Humanizer:
"Natural writing that preserves the user's meaning and voice."

Platform:
"The best Dutch + English writing-authenticity and writing-improvement system."

---

# 26. Recommended Build Priority

P0
- HumanBench-NL/EN
- detector dataset
- detector baseline
- calibration
- false-positive testing

P1
- sentence detector
- mixed-authorship detector
- Dutch/English domain calibration
- detector UI

P2
- humanizer
- meaning preservation
- tone controls
- sentence variation
- vocabulary naturalization

P3
- Style DNA
- A/B/C rewriting
- personalization
- preference learning

P4
- integrations
- API
- enterprise
- more languages

---

# Final Product Principle

Detection should be probabilistic, transparent, and conservative.

Humanization should focus on:
- naturalness
- clarity
- rhythm
- personalization
- meaning preservation
- locale accuracy
- user voice

The strongest long-term advantage is not a single model.
It is the combination of:
DATA + EVALUATION + PERSONALIZATION + TRUST.
