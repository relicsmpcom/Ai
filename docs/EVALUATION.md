# Evaluation

> **These numbers measure the pipeline, not the product.**
>
> They come from the HumanBench-NL/EN *seed* corpus, every document of which
> was written for this repository by an AI model imitating each register —
> including the documents labelled human. That makes the benchmark easier than
> reality in exactly the direction that flatters a detector. Read
> [`wia/data/humanbench/DATA_CARD.md`](../wia/data/humanbench/DATA_CARD.md)
> before quoting anything here.
>
> Regenerate with `wia bench --cv 5 --split test --markdown docs/EVALUATION.md`.

## How to read this

The headline is **not** accuracy. It is the false-positive rate and the
hard-negative slice, because the failure that hurts a real person is a detector
telling them their own writing was generated.

The current model trades recall for that safety: one document in five is
returned as *uncertain* rather than guessed at, and the AI class is only
committed to when the evidence clears a threshold fitted to hold false
positives at 1%. Ranking is strong, so the evidence is there — the decision
policy is deliberately refusing to spend it. Mixed authorship is the weakest
class by a wide margin and needs span-level labels and longer documents before
it will work.

---

# Detector evaluation — 5-fold cross-validation (out of fold)

Samples: **151**

## Safety first

| metric | value |
| --- | --- |
| False-positive rate (human called AI) | 0.000 |
| Human text called AI *or* mixed | 0.012 |
| TPR @ 1% FPR | 0.354 |
| TPR @ 5% FPR | 0.708 |
| Answers withheld as uncertain | 0.219 |

## Discrimination and calibration

| metric | value |
| --- | --- |
| ROC-AUC (AI vs rest) | 0.905 |
| Macro F1 | 0.492 |
| Expected calibration error | 0.148 |

## Per class

| class | precision | recall | F1 | n |
| --- | --- | --- | --- | --- |
| human | 0.755 | 0.835 | 0.793 | 85 |
| mixed | 0.333 | 0.111 | 0.167 | 18 |
| ai | 0.944 | 0.354 | 0.515 | 48 |

## Hard negatives

Human writing chosen because it *looks* generated: non-native writers, legal and policy prose, plain-language public information, translated text, grammar-checked writing.

- samples: **24**
- wrongly called AI: **0**
- called mixed: **1**
- held as human or uncertain: **23**
  - `lg-h-005` (en, university, 193w) → mixed (p_ai=0.47)

## By language

| slice | n | macro F1 | ROC-AUC | FPR | uncertain |
| --- | --- | --- | --- | --- | --- |
| en | 76 | 0.498 | 0.906 | 0.000 | 0.237 |
| nl | 75 | 0.472 | 0.906 | 0.000 | 0.200 |

## By length

| slice | n | macro F1 | ROC-AUC | FPR | uncertain |
| --- | --- | --- | --- | --- | --- |
| 100-250 | 10 | 0.345 | 0.833 | 0.000 | 0.100 |
| 20-50 | 23 | 0.172 | 0.987 | 0.000 | 0.478 |
| 250-500 | 1 | 0.333 | n/a | 0.000 | 0.000 |
| 50-100 | 117 | 0.520 | 0.910 | 0.000 | 0.179 |

## Confusion (rows = actual)

| actual \ predicted | human | mixed | ai | uncertain |
| --- | --- | --- | --- | --- |
| human | 71 | 1 | 0 | 13 |
| mixed | 11 | 2 | 1 | 4 |
| ai | 12 | 3 | 17 | 16 |
| uncertain | 0 | 0 | 0 | 0 |


# Detector evaluation — test

Samples: **22**

## Safety first

| metric | value |
| --- | --- |
| False-positive rate (human called AI) | 0.000 |
| Human text called AI *or* mixed | 0.000 |
| TPR @ 1% FPR | 0.857 |
| TPR @ 5% FPR | 0.857 |
| Answers withheld as uncertain | 0.273 |

## Discrimination and calibration

| metric | value |
| --- | --- |
| ROC-AUC (AI vs rest) | 0.990 |
| Macro F1 | 0.482 |
| Expected calibration error | 0.263 |

## Per class

| class | precision | recall | F1 | n |
| --- | --- | --- | --- | --- |
| human | 0.846 | 0.846 | 0.846 | 13 |
| mixed | 0.000 | 0.000 | 0.000 | 2 |
| ai | 1.000 | 0.429 | 0.600 | 7 |

## Hard negatives

Human writing chosen because it *looks* generated: non-native writers, legal and policy prose, plain-language public information, translated text, grammar-checked writing.

- samples: **4**
- wrongly called AI: **0**
- called mixed: **0**
- held as human or uncertain: **4**

## By language

| slice | n | macro F1 | ROC-AUC | FPR | uncertain |
| --- | --- | --- | --- | --- | --- |
| en | 11 | 0.452 | 1.000 | 0.000 | 0.273 |
| nl | 11 | 0.500 | 1.000 | 0.000 | 0.273 |

## By length

| slice | n | macro F1 | ROC-AUC | FPR | uncertain |
| --- | --- | --- | --- | --- | --- |
| 100-250 | 2 | 0.667 | 1.000 | 0.000 | 0.000 |
| 20-50 | 3 | 0.167 | n/a | 0.000 | 0.667 |
| 50-100 | 17 | 0.467 | 0.985 | 0.000 | 0.235 |

## By domain

| slice | n | macro F1 | ROC-AUC | FPR | uncertain |
| --- | --- | --- | --- | --- | --- |
| blog | 2 | 0.333 | n/a | 0.000 | 0.000 |
| business_email | 1 | 0.333 | n/a | 0.000 | 0.000 |
| chat | 1 | 0.333 | n/a | 0.000 | 0.000 |
| customer_support | 1 | 0.333 | n/a | 0.000 | 0.000 |
| journalism | 4 | 0.333 | 1.000 | 0.000 | 0.500 |
| marketing | 2 | 0.000 | n/a | n/a | 0.000 |
| product_description | 2 | 0.000 | n/a | n/a | 1.000 |
| report | 4 | 0.667 | 1.000 | 0.000 | 0.000 |
| school_essay | 2 | 0.333 | n/a | n/a | 0.000 |
| social | 2 | 0.000 | n/a | 0.000 | 1.000 |
| university | 1 | 0.333 | n/a | 0.000 | 0.000 |

## By provenance

| slice | n | macro F1 | ROC-AUC | FPR | uncertain |
| --- | --- | --- | --- | --- | --- |
| ai_light_human_edit | 2 | 0.000 | n/a | n/a | 1.000 |
| fully_ai | 5 | 0.250 | n/a | n/a | 0.400 |
| fully_human | 13 | 0.306 | n/a | 0.000 | 0.154 |
| human_heavily_ai_edited | 2 | 0.000 | n/a | n/a | 0.000 |

## Confusion (rows = actual)

| actual \ predicted | human | mixed | ai | uncertain |
| --- | --- | --- | --- | --- |
| human | 11 | 0 | 0 | 2 |
| mixed | 2 | 0 | 0 | 0 |
| ai | 0 | 0 | 3 | 4 |
| uncertain | 0 | 0 | 0 | 0 |
