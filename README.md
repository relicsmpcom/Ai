# WIA — Writing Intelligence Assistant

**Dutch + English. Detector first, humanizer second.**

An implementation of the platform in [`docs/ROADMAP.md`](docs/ROADMAP.md): a
system that estimates how a text was likely produced, and improves writing
without changing what it says.

```
                    ┌──────────────┐
        text ─────▶ │   detector   │──▶ calibrated estimate + span heatmap
                    ├──────────────┤
                    │   analyzer   │──▶ rhythm, vocabulary, tone, issues
                    ├──────────────┤
                    │  humanizer   │──▶ A / B / C rewrites, meaning-checked
                    ├──────────────┤
                    │  HumanBench  │──▶ the evaluation everything answers to
                    └──────────────┘
```

## What it does and does not claim

It estimates. It does not prove. Every detection result carries a probability,
a confidence, an explanation of what moved it, and a warning when the text is
the kind that detectors get wrong.

It is **not** built to make text undetectable. The naturalness critic never
consults the detector, and the humanizer never optimises against it — see
[Two rules we did not bend](#two-rules-we-did-not-bend).

## Quick start

```bash
pip install -e ".[api,dev]"

wia detect essay.txt
wia humanize draft.txt --mode zakelijk_nederlands --locale nl-NL
wia analyze post.md
wia compare original.txt rewrite.txt
wia style my-emails/*.txt --out me.json
wia bench --cv 5
wia serve                       # API + web UI on http://127.0.0.1:8000
```

The core package has **no dependencies**. `fastapi` and `uvicorn` are needed
only for `wia serve`; `pytest` only for the tests.

## The four systems

### 1. Detector

51 named measurements — rhythm, lexis, syntax, discourse, orthography,
statistics — feed a calibrated linear ensemble that reports three classes:
human, mixed, AI. Everything it measures is published at `GET /features` and
`wia features`; nothing about it is a secret.

Three things it does that most detectors do not:

* **It refuses.** Under 40 words there is no verdict at all, and no text under
  120 words can be called "likely AI". Confidence scales with evidence.
* **It recognises the people it would otherwise hurt.** Non-native writers in
  formal register, legal and policy prose, plain-language public information,
  translated text, grammar-checked writing — each is detected as a
  *false-positive risk profile*, and the estimate is damped and explained
  rather than delivered with confidence.
* **It explains itself.** Every result names the measurements that moved it,
  with their direction, from the model's actual weights.

Segment analysis scores overlapping sentence windows, which is what makes the
heatmap and the mixed-authorship summary possible — and it never scores a lone
sentence, because a sentence carries almost no evidence.

### 2. Humanizer

27 rewrite operations across six passes, three candidates per request:

| | |
| --- | --- |
| **A** | closest to your original — surface only, no restructuring |
| **B** | most natural — the full plan at normal strength |
| **C** | strongest style adaptation |
| **D** | model-assisted, when a backend is configured — judged identically |

Meaning preservation is a **gate, not a score**. Before any candidate is
offered, the rewrite is compared against the source on numbers, dates, times,
names, citations, URLs, reference numbers, quotations, sentence polarity and
how certain the writer sounded. Anything that moved is rejected, retried more
gently, and if it still fails, your original is handed back unchanged with the
reason.

Quotations, URLs, code identifiers and anything you list in `preserve` are
masked before an operation can touch them. Operations cannot damage what they
cannot see.

Controls follow the roadmap: tone (15), formality (1–6), directness,
conciseness, complexity (A2–academic), vocabulary, contractions, idioms,
audience, purpose, emotional colour, sentence variation, locale, plus 27 named
modes for Dutch and English.

### 3. Analyzer

What is actually going on in a text: readability, rhythm and its distribution,
vocabulary variety, tone and formality, structure, and a list of concrete
issues — flat rhythm, repeated openings, abstract vocabulary, restatement,
mixed `je`/`u` register, mixed US/UK spelling, paragraphs that are all the
same size.

### 4. HumanBench-NL/EN

A benchmark with a ten-point provenance spectrum rather than a human/AI
binary, thirteen domains, four length buckets, and a 24-document hard-negative
slice. Spelling and grammar correction map to **human**, because treating a
spell checker as co-authorship is how a detector ends up penalising dyslexic
and non-native writers for using accessibility tools.

**The shipped corpus is a seed corpus and is AI-authored throughout, including
the documents labelled human.** It exists to make the pipeline runnable and
testable, not to measure detection quality. Read
[`wia/data/humanbench/DATA_CARD.md`](wia/data/humanbench/DATA_CARD.md) before
quoting a number from it.

## Results

Cross-validated on the seed corpus (`wia bench --cv 5`), with the caveat above
applying to every figure:

| | |
| --- | --- |
| False-positive rate (human called AI) | **0.000** |
| Hard negatives wrongly accused | **0 / 24** |
| ROC-AUC (AI vs rest) | 0.905 |
| TPR @ 1% FPR | 0.354 |
| TPR @ 5% FPR | 0.708 |
| Expected calibration error | 0.148 |
| Answers withheld as uncertain | 0.219 |

The recall is low because the decision policy is deliberately refusing to
spend evidence it has. Ranking is strong; committing is not. That is the right
default for a system people point at other people's work, and it is a knob
(`wia train --target-fpr`) rather than a law.

Humanizer, over the same corpus: **151 / 151** rewrites preserve meaning, no
grammar regressions, mean naturalness **+3.8** on generated text and **+0.1**
on human text — it improves what is flat and leaves good writing alone.

Full report: [`docs/EVALUATION.md`](docs/EVALUATION.md).

## Two rules we did not bend

**The naturalness critic never consults the detector.** Scoring rewrites by how
well they fool detection would make this an evasion tool, and it would corrupt
the detector's own evaluation loop — the two systems would train on each other
until neither measured anything. Naturalness is scored on variation, plainness,
flow, moderation and shape: qualities that make writing better for a reader.
Whether that also changes a detector's opinion is a side effect nobody here
optimises for. The Compare screen shows the AI-probability delta *for
information*, and says so.

**Dutch is written for Dutch, not translated into it.** Dutch is verb-second,
so removing a fronted adverbial breaks the sentence: *"Bovendien speelt
technologie een rol"* → *"Speelt technologie een rol"*. The pipeline detects
the inversion and repairs it (*"Technologie speelt een rol"*), and when it
cannot do so confidently it declines the edit instead of shipping broken
Dutch. Contractions get the same treatment: English has a regular clitic
system and Dutch does not, so `'t` and `zo'n` are applied sparingly and only in
genuinely informal registers.

## API

```
POST /detect          text → probabilities, confidence, heatmap, warnings
POST /humanize        text + controls → candidates with scores and meaning reports
POST /analyze         text → metrics and issues
POST /compare         two texts → deltas and a meaning verdict
POST /meaning-check   two texts → the guard on its own
POST /style-profile   samples → a Style DNA profile
GET  /features        every measurement and operation, documented
GET  /modes           the named humanizer modes
GET  /health          what is loaded, including the decision thresholds
GET  /                the web UI
```

## Layout

```
wia/
  text/        tokenisation, NL/EN sentence segmentation, windows
  lang/        Dutch/English identification
  features/    the 51-measurement battery + marker lexicons
  detector/    model, calibration, decision policy, risk profiles, pipeline
  meaning/     anchors and the preservation guard
  humanizer/   options, modes, planner, 27 operations, critics, Style DNA
  analyze/     the writing analyzer
  bench/       HumanBench schema, metrics, training, evaluation
  api/         FastAPI service
  data/        the seed corpus + its data card
  web/         the single-file UI
tests/         105 tests
docs/          roadmap, roadmap status, architecture, evaluation
```

## Status against the roadmap

Phases A through the humanizer MVP are implemented; the transformer classifier,
the preference model, the integrations and the real data collection are not.
[`docs/ROADMAP_STATUS.md`](docs/ROADMAP_STATUS.md) goes section by section and
says plainly which is which.

## Licence

MIT.
