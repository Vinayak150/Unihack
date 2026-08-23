# Evaluation Report — run `cli-eval`

- Total rows processed: **1000**
- Ground-truth rows matched: **2** (only rows present in `ground_truth_delivery_format.csv` can be scored for field accuracy — see docs/evaluation.md for why this is currently small)

## Field accuracy (against verified ground truth)

| Field | Correct / Total | Accuracy |
|---|---|---|
| MANUFACTURER_NAME | 2/2 | 100% |
| BRAND_NAME | 2/2 | 100% |
| Classpath | 2/2 | 100% |
| Dept | 2/2 | 100% |
| Class | 2/2 | 100% |
| Fine | 2/2 | 100% |
| Product Name | 2/2 | 100% |

## Batch coverage & quality (full input, no ground truth needed)

| Metric | Value |
|---|---|
| manufacturer_resolution_rate | 0.961 |
| classification_resolution_rate | 0.268 |
| validation_pass_rate | 0.961 |
| review_rate | 0.771 |
| avg_confidence | 0.6757 |
| groundedness_rate | 0.6949 |
| lov_mismatch_count | 1 |

## Status distribution

| Status | Count |
|---|---|
| PARTIAL | 229 |
| UNRESOLVED | 704 |
| VALIDATION_FAILED | 39 |
| REVIEW_REQUIRED | 28 |