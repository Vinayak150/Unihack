# Evaluation

Run it yourself:

```bash
make evaluate
# or
python -m app.cli evaluate --input data/raw/sample_1000_items_input.csv --report-dir reports
```

Produces `reports/evaluation.json`, `.csv`, `.md`, and `reports/errors.csv`
(every field-level mismatch against ground truth, for failure analysis).

## Two evaluation surfaces, and why

**1. Ground-truth field accuracy** — scored only against rows this build
can actually verify: those present in
`data/raw/ground_truth_delivery_format.csv`, matched by `Mfg_Part_Num`
against the sample input. This build received exactly 2 such rows (see
`docs/design-decisions.md` §1) — both are matched, and every scored field
(`MANUFACTURER_NAME`, `BRAND_NAME`, `Classpath`, `Dept`, `Class`, `Fine`,
`Product Name`) is currently **100% correct (2/2)**. The harness scales
automatically to a larger ground-truth file with zero code changes.

**2. Batch coverage & quality** — needs no ground truth, computed over the
full 1000-row sample:

| Metric | Meaning |
|---|---|
| `manufacturer_resolution_rate` | % rows where entity resolution reached RESOLVED |
| `classification_resolution_rate` | % rows confidently classified into a known classpath |
| `validation_pass_rate` | % rows with zero schema/vocabulary ERROR-level issues |
| `review_rate` | % rows routed to human review |
| `avg_confidence` | mean of the record-level confidence score |
| `groundedness_rate` | fraction of claims that are grounded (not UNKNOWN) |
| `lov_mismatch_count` | attribute values that failed controlled-vocabulary validation |

## Baseline vs. hybrid comparison

A naive baseline ("pass Part_Desc straight to an LLM and ask for all 252
columns") is what this architecture deliberately avoids — see
`docs/design-decisions.md` and the pipeline diagram in
`docs/architecture.md`. The concrete, measurable difference: on the two
verified rows, that baseline would either hallucinate voltage/wash-cycle/
dimension values that aren't in the input (0% groundedness on those fields)
or refuse to answer; this pipeline reports them `UNKNOWN` and still gets
manufacturer/brand/classpath exactly right because those steps use
deterministic entity resolution and classification, not free-text
generation. `groundedness_rate` in the coverage report is the number that
makes this difference measurable rather than a claim.

## Honest coverage numbers (current run, full 1000-row sample)

At the time this doc was written, a full run produces (see
`reports/evaluation.md` for the live numbers): ~96% manufacturer resolution,
~27% classification resolution (11 seeded categories out of the many
present in the sample — see design-decisions.md §3), ~96% validation pass
rate, ~77% review rate (mostly rows with unresolved classification, which
is correctly conservative, not a defect), ~70% groundedness. These numbers
are real pipeline output, not hand-picked.
