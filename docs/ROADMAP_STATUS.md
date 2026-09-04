# Roadmap status

Section by section against [`ROADMAP.md`](ROADMAP.md). ✅ built · 🟡 partial ·
⬜ not built. "Partial" always says what is missing.

## §1–2 Vision and development order

✅ Detector first, benchmark before humanizer, humanizer second — built in that
order, and the commit history shows it. The positioning is enforced in code:
nothing optimises for undetectability, and the naturalness critic is
architecturally forbidden from consulting the detector.

## §3 HumanBench-NL/EN

🟡 **Schema, slices and harness: built. Data: a seed corpus only.**

| | |
| --- | --- |
| ✅ | Ten-point provenance spectrum, with the collapse to three reported classes in one visible place |
| ✅ | Both languages, 13 domains, 4 length buckets, register and locale fields |
| ✅ | Hard-negative slice (24 documents) reported separately |
| ✅ | Schema validation that runs in the test suite |
| 🟡 | 151 documents, ~11k words — enough to exercise the pipeline, far too few to measure anything |
| ⬜ | Real consented human writing with provenance attested at collection time |
| ⬜ | Belgian/Flemish Dutch collected as its own slice (the locale field exists; the data does not) |
| ⬜ | Multiple generator models, with post-training-cutoff models held out |
| ⬜ | Span-level labels for genuinely mixed documents |
| ⬜ | 500–1000 and 1000+ length buckets |

The data card is explicit that the seed corpus is AI-authored throughout and
what would have to exist before any number from it is quotable.

## §4 Detector V1

| Roadmap component | Status |
| --- | --- |
| Language detection | ✅ function-word + orthographic n-gram identification, declines to guess |
| Neural text classifier | ⬜ **not built** — the slot exists in the ensemble; the linear model is the baseline it has to beat |
| Stylometric feature model | ✅ 51 named measurements |
| Statistical / probability features | 🟡 redundancy gain, repetition, overlap, entropy proxies — no token-level surprisal (that needs a language model) |
| Sentence variation analysis | ✅ |
| Paragraph consistency analysis | ✅ |
| Domain classifier | ✅ 10 domains, heuristic |
| Calibration layer | ✅ temperature fitted on *delivered* probabilities, not raw logits |
| Final authorship estimate | ✅ six output classes including Uncertain |

## §5 Sentence-level detection

✅ Overlapping sentence windows (60 words, 30-word stride), per-span
probabilities with a reliability weight, heatmap in the UI, mixed-authorship
summary with switch count and disagreement.

Every signal the roadmap lists is implemented as a feature except token
predictability. No rule anywhere is of the form "uses word X = AI": the marker
lexicons are counted as *family densities*, and no single feature can carry a
verdict.

## §6–7 Dutch- and English-specific work

🟡 The hard negatives named in the roadmap exist in the corpus and are reported
as their own slice: non-native writers, plain/simplified language, highly
formal Dutch, legal Dutch and English, academic prose, translated text,
grammar-corrected writing, wire copy, reference documentation, B2B boilerplate.
Dutch-specific handling (compounds, separable verbs, modal particles, `je`/`u`
register, Flemish vocabulary) is implemented in the features and the humanizer.

⬜ What is missing is *real* writers in those categories. Testing a
false-positive profile against documents written by a model imitating that
profile proves very little.

## §8 Detector metrics

✅ All of them: TPR@1%FPR, TPR@5%FPR, ROC-AUC, precision, recall, F1,
expected calibration error, reliability table, per-language, per-domain,
per-length and per-provenance breakdowns, plus two metrics the roadmap implies
but does not name — the rate at which human text is called *anything but*
human, and the rate at which the system declines to answer.

Generic accuracy is never reported as a headline. `wia bench` leads with the
false-positive rate.

## §9–10 Humanizer V1 and its methods

✅ The pipeline, and 27 operations covering: sentence variation, natural
transitions, vocabulary naturalisation, contraction control, rhythm,
paragraph restructuring, redundancy reduction, directness, register matching,
locale matching, formality shifting, conciseness, complexity, audience and
purpose adaptation, style preservation, Style DNA, and multi-pass rewriting.

Two of the roadmap's methods are deliberately narrower than written:

* **Personal voice (§10.E)** preserves and surfaces the voice already in the
  text. It never adds an opinion or an experience, because the roadmap's own
  "never invent personal experiences" is easier to honour by never inventing.
* **Specificity improvement (§10.I)** reports where a text is vague instead of
  making it concrete, because a rewriter that invents detail to sound specific
  is a hallucination engine. The roadmap says "do not invent facts"; the only
  reliable way to obey that is to leave generality alone.

⬜ Idiom insertion (§10.O) is implemented as *control* (locale-aware
vocabulary), not as generation — the system never forces an idiom in.

## §11 Specialized modes

✅ All 11 Dutch modes, all 11 English modes, and the 5 Style DNA modes, as
named option bundles that the user can still override control by control.

## §12–13 Meaning preservation and factuality guard

✅ The most complete part of the build. Anchors extracted and compared:
numbers (locale-normalised so `1.420.000` and `1,420,000` are the same
number), dates, times, names, citations, URLs, reference identifiers,
technical terms, quotations, sentence polarity, certainty level, content
coverage and length collapse. Violations are typed, weighted and marked
blocking or not, and the roadmap's worked example — "grew approximately 18%"
becoming "grew more than 20%" — is a test.

## §14 Quality score

✅ All nine components, reported separately and combined, with meaning acting
as a gate rather than a term: a rejected rewrite scores zero overall no matter
how well it reads.

## §15 A/B/C candidates

✅ Three candidates at three intensities, plus a fourth from a model backend
when one is configured. ⬜ Preference capture and the preference model are not
built — the API returns everything a client would need to log a choice, but
nothing is stored server-side. That is a deliberate stopping point: storing
preference data needs consent handling this repository does not have.

## §16 Mixed-language handling

✅ Code-switching is detected and reported as a risk factor rather than
"corrected"; brand names, product names and technical terms are protected from
rewriting.

## §17 Safety constraints

✅ Enforced in code, not just documented. The naturalness critic cannot see the
detector. The `/humanize` response carries the statement in every payload. The
Compare screen labels the AI-probability delta as information only.

## §18 UX

🟡 Detect, Humanize, Analyze, Compare and My Style are built as a working
single-page UI with every control, the span heatmap, per-candidate scores and
a change log. ⬜ History and API-key management screens are not built (there
are no accounts).

## §19 Technical stack

🟡 Python + FastAPI as specified. The frontend is a dependency-free single-page
app rather than Next.js — the trade was a UI that runs today over a scaffold
that needs a build step. PostgreSQL, Redis, Celery, MLflow and PostHog are not
present; nothing yet persists across requests, so they would be furniture.

## §20 Model architecture

🟡 Ensemble structure, calibration model and per-language models are built. The
transformer classifier is the significant gap, and the honest framing is that
the linear model is the baseline it must beat on HumanBench before it ships.
The humanizer's model router exists (`wia/humanizer/llm.py`) with an Anthropic
backend, off by default.

## §21 API design

✅ `/detect`, `/humanize`, `/compare`, `/analyze`, `/style-profile`, plus
`/meaning-check`, `/features`, `/modes` and `/health`.

## §22 First MVP

✅ Detector MVP complete except the calibration *dashboard* (the numbers are
produced; there is no UI for them). ✅ Humanizer MVP complete.

## §23 12-month roadmap

Months 1–6 are substantially built as a working prototype, on a seed corpus
instead of collected data. Months 7–12 (preference learning, extensions,
public API with accounts, enterprise, external benchmark publication) are not
started.

## §24 Moat

The parts of the moat that are code — the evaluation harness, the
meaning-preservation evaluator, domain calibration, transparent uncertainty,
Style DNA — are built. The parts that are *data* are, by definition, not
something a repository can contain. That gap is the whole project.

## The honest summary

What exists is a complete, tested, runnable implementation of the architecture,
with the measurement discipline the roadmap asks for and a set of safety
decisions made in code rather than in a policy document.

What does not exist is the data. Every detection number in this repository is
measured on documents written by a model, and that makes them a test of the
plumbing rather than evidence about the world. The next real step is not a
better model — it is the collection described in §3 of the data card.
