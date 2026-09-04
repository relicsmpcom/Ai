# Architecture

## Layers

```
             ┌───────────────────────────────────────────────┐
  wia/web    │            wia.api  (FastAPI)                 │
  ───────────┴───────────────────┬───────────────────────────┘
                                 │
    ┌──────────────┬─────────────┼──────────────┬──────────────┐
    │              │             │              │              │
 detector      humanizer      analyze         bench         meaning
    │              │             │              │              │
    └──────────────┴──────┬──────┴──────────────┘              │
                          │                                    │
                     features (51) ◀───────────────────────────┘
                          │
                 text · lang · lexicons
```

Every layer depends only downward. `features` is the shared vocabulary: the
detector classifies with it, the analyzer reports it, the humanizer's planner
decides from it, and the critics score with it. One consequence worth stating:
adding a measurement improves all four systems at once, and a bug in one
measurement is a bug in all four — which is why the feature battery has its own
tests.

## The detector path

```
text
 ├─ detect_language          function words + character n-grams; may decline
 ├─ classify_domain          10 genres — support macros are formulaic by design
 ├─ extract(Doc)             51 measurements
 ├─ standardize              z-scores against trained stats (priors as fallback)
 ├─ model.predict            multinomial logistic → human / mixed / ai
 ├─ shrink_toward_human      short texts carry less evidence, and say so
 ├─ risk.assess + dampen     hard-negative profiles pull the estimate back
 ├─ policy.decide            asymmetric thresholds + evidence floors
 ├─ windows → segments       overlapping 60-word spans, never a lone sentence
 └─ explain                  weight × value for the winning class
```

Three design decisions carry most of the safety:

**Calibration is fitted on delivered probabilities.** Temperature is chosen by
running the *whole pipeline* on the dev split — shrinkage and damping
included — and minimising the negative log-likelihood of the numbers the user
actually sees. Calibrating raw logits would produce a well-calibrated number
that nothing displays.

**Thresholds are fitted out-of-fold, with floors.** `likely_ai` is the lowest
probability that holds the false-positive rate at or under target across
five-fold out-of-fold predictions — and it may never fall below a conservative
default while the held-out human sample is small. An FPR of 0% over seventy
documents is a statement about seventy documents.

**Evidence floors are absolute.** Under 40 words: no verdict. Under 120 words:
no strong verdict. These are not probabilities and cannot be overridden by one.

## The humanizer path

```
text
 ├─ analysis          language, features, style profile
 ├─ build_plan        pick operations from what is wrong with THIS text
 ├─ protect           mask quotes, URLs, code, reference numbers, preserve list
 ├─ candidates A/B/C  same plan at three intensities, seeded RNG
 │    └─ 6 passes     trimming → structure → rhythm → style → locale → grammar
 ├─ restore           unmask
 ├─ critics           meaning gate · naturalness · grammar delta · tone · locale
 ├─ repair            one gentler retry for anything the gate rejected
 └─ rank              best accepted candidate wins; original is the fallback
```

**Meaning is a gate, not a score.** A rewrite that moved a number is not a
worse rewrite, it is not a rewrite — it scores zero and cannot be recommended.

**The grammar critic measures damage, not style.** It compares issues in the
rewrite against issues already in the original, so a writer who uses lower-case
sentence starts is never penalised for their own voice.

**Protection beats detection.** Quotations, URLs, code identifiers and
user-listed phrases are masked with non-printing sentinels before any operation
runs. The guard would catch damage to them anyway; a rewrite that never breaks
a quote is better than one that gets rejected and retried.

## Where a model plugs in

`wia/humanizer/llm.py` defines `RewriteBackend`. A configured backend produces
one more candidate, which goes through the identical gate and critics. The
default is `NullBackend`, so the system runs offline and deterministically.

The detector has an equivalent, unfilled slot: `LinearModel` is a baseline that
a transformer classifier should beat on HumanBench before replacing it. The
ensemble structure, the calibration layer and the decision policy do not care
which model produces the scores.

## Determinism

Given the same input, options and seed, the humanizer produces byte-identical
output. Every random choice goes through `Context.rng`, seeded from
`options.seed` plus the candidate label. This is what makes rewrites
reviewable and the tests meaningful.

## Adding things

**A feature:** decorate a function in `wia/features/extractors.py` with
`@feature(name, group, doc, center, spread, direction)`. It joins the vector,
the API's `/features` listing, the explanations and the analyzer automatically.
Retrain afterwards — feature distributions are part of the model.

**A rewrite operation:** decorate a function in `wia/humanizer/ops/` with
`@op(name, doc, order, group)` and teach `build_plan` when to want it. Order
places it in one of the six passes.

**A language:** the honest answer is that it is not a plug-in. Dutch needed its
own segmentation guards, its own function-word inventory, its own contraction
policy and its own verb-second repair. A third language needs the same care,
and the seams are marked `is_nl` so they are easy to find.
