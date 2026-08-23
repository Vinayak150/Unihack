from app.evaluation.evaluator import evaluate


def test_evaluator_matches_verified_rows_and_scores_them_perfectly():
    report, results, output_records = evaluate(run_id="pytest-eval")
    assert report.total_rows == 1000
    assert report.ground_truth_rows_matched == 2
    for field in ("MANUFACTURER_NAME", "BRAND_NAME", "Classpath"):
        acc = report.field_accuracy[field]
        assert acc["total"] == 2
        assert acc["correct"] == 2


def test_evaluator_coverage_metrics_are_sane_fractions():
    report, _, _ = evaluate(run_id="pytest-eval-2")
    for key in ("manufacturer_resolution_rate", "classification_resolution_rate", "validation_pass_rate", "review_rate", "groundedness_rate"):
        assert 0.0 <= report.coverage[key] <= 1.0
