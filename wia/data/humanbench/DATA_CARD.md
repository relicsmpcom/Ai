# HumanBench-NL/EN — seed corpus

**Read this before you quote a number from this benchmark.**

## What this is

A 151-document seed corpus for Dutch and English, used to make the detector
pipeline runnable, testable and inspectable end to end. It defines the schema,
the label space, the slices and the evaluation contract that the real
benchmark will use.

## What this is not

It is **not** a validated benchmark, and results measured on it are **not**
evidence that the detector works on real text.

Every document in it — including the ones labelled `fully_human` — was written
for this repository by an AI model imitating each register. That is a serious
limitation and it points one way: it makes the benchmark *easier* than
reality. The "human" documents contain the irregularities a model believes
human writing has, and the detector is partly rewarded for recognising that
belief. Real human writing is messier, more varied, and more often looks
formulaic for perfectly innocent reasons.

Treat every metric produced from this corpus as a **smoke test of the
pipeline**, not as a measurement of detection quality.

## Composition

| axis | contents |
| --- | --- |
| Languages | Dutch (nl-NL, some nl-BE vocabulary), English (en-GB, en-US, en-INT) |
| Documents | 151 (~11,100 words) |
| Coarse classes | human 85, mixed 18, ai 48 |
| Provenance labels | all 10 points of the spectrum except `uncertain` |
| Domains | 13 (email, essay, university, support, report, blog, journalism, marketing, product, social, chat, technical docs, creative) |
| Length buckets | 20–50, 50–100, 100–250, 250–500 |
| Splits | train 99, dev 30, test 22 |
| Hard negatives | 24 documents tagged `hard_negative` |

The `hard_negative` slice is the important one. It holds human writing chosen
because it *looks* generated: non-native writers in formal register,
grammar-checked text, Dutch and English contract clauses, government
plain-language (B1) information, translated manuals, wire-service copy,
reference documentation, B2B boilerplate. These are the documents a careless
detector accuses, and they are the ones a person would have to defend
themselves against.

## Labelling

Provenance uses the ten-point spectrum in `wia/bench/dataset.py`. The mapping
down to the three reported classes lives in `COARSE_MAP` and encodes two
product decisions worth arguing about:

* **Spelling and grammar correction stay human.** A spell checker is not a
  co-author. Treating it as one is how a detector ends up penalising dyslexic
  and non-native writers for using accessibility tools.
* **A generated draft that a person rewrote heavily counts as mixed**, not as
  AI, because a reader would recognise the person in the result.

## Building the real thing

The seed corpus is a placeholder for the data collection the roadmap puts at
P0. A usable HumanBench needs, at minimum:

1. **Consented human writing with provenance attested at collection time** —
   not inferred later. Ask the writer what tools they used, before you have an
   opinion about the text.
2. **Timestamped pre-2022 human text** as an uncontaminated baseline.
3. **Writers who are the false-positive risk**, recruited deliberately:
   non-native Dutch and English writers, dyslexic writers, people who write in
   legal, academic and government registers, translators.
4. **Multiple generator models**, including ones released after the detector
   was trained, held out entirely (cross-model robustness cannot be measured
   on generators you trained on).
5. **Real mixed authorship with span-level labels** — a person's edit history,
   not a document someone assembled to look mixed.
6. **Belgian/Flemish Dutch collected separately** from Netherlands Dutch.
7. **Per-document licence and consent records**, and a deletion path.

Until at least (1), (3) and (4) exist, no number from this repository should
appear in marketing copy.
