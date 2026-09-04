import math

import pytest

from wia.bench import Dataset, run_cross_validation, run_eval, validate
from wia.bench.dataset import COARSE_MAP, Provenance, length_bucket
from wia.bench.metrics import evaluate, roc_auc, tpr_at_fpr


def test_corpus_is_valid_and_balanced():
    ds = Dataset.load()
    assert not validate(ds.samples)
    summary = ds.summary()
    assert summary["samples"] >= 140
    assert set(summary["language"]) == {"nl", "en"}
    # Neither language may be a footnote to the other.
    nl, en = summary["language"]["nl"], summary["language"]["en"]
    assert min(nl, en) / max(nl, en) > 0.8
    assert summary["splits"]["test"] >= 15


def test_every_provenance_class_maps_somewhere_explicit():
    for provenance in Provenance:
        assert provenance in COARSE_MAP
    assert COARSE_MAP[Provenance.HUMAN_SPELLCHECK] == "human"
    assert COARSE_MAP[Provenance.HUMAN_GRAMMAR_CORRECTION] == "human"
    assert COARSE_MAP[Provenance.UNCERTAIN] is None


def test_hard_negative_slice_exists_and_is_all_human():
    hard = [s for s in Dataset.load() if "hard_negative" in s.tags]
    assert len(hard) >= 20
    assert all(s.coarse == "human" for s in hard)


@pytest.mark.parametrize("words,bucket", [
    (30, "20-50"), (75, "50-100"), (200, "100-250"), (400, "250-500"),
    (700, "500-1000"), (2000, "1000+"),
])
def test_length_buckets(words, bucket):
    assert length_bucket(words) == bucket


def test_roc_auc_matches_a_known_case():
    assert roc_auc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0
    assert roc_auc([1, 2, 3, 4], [1, 1, 0, 0]) == 0.0
    assert abs(roc_auc([1, 2, 3, 4], [0, 1, 0, 1]) - 0.75) < 1e-9
    assert math.isnan(roc_auc([1, 2], [1, 1]))


def test_tpr_at_fpr_respects_the_budget():
    scores = [0.9, 0.8, 0.7, 0.6, 0.2, 0.1]
    labels = [1, 1, 0, 1, 0, 0]
    tpr, threshold = tpr_at_fpr(scores, labels, 0.0)
    assert tpr == pytest.approx(2 / 3)
    assert threshold >= 0.8


def test_evaluate_reports_the_dangerous_number():
    result = evaluate(
        ai_scores=[0.9, 0.1, 0.2], is_ai=[1, 0, 0],
        predicted=["ai", "human", "ai"], actual=["ai", "human", "human"],
        top_prob=[0.9, 0.8, 0.6],
    )
    assert result.false_positive_rate == pytest.approx(0.5)
    assert result.per_class["ai"]["precision"] == pytest.approx(0.5)


def test_held_out_evaluation_keeps_false_positives_at_zero():
    report = run_eval(split="test")
    metrics = report["metrics"]
    assert metrics["false_positive_rate"] == 0.0
    assert report["hard_negatives"]["accused_as_ai"] == 0


def test_cross_validated_ranking_is_far_better_than_chance():
    report = run_cross_validation(folds=5)
    assert report["metrics"]["roc_auc_ai"] > 0.80
    assert report["metrics"]["false_positive_rate"] < 0.02
    assert report["hard_negatives"]["accused_as_ai"] == 0
