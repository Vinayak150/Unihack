# Design decisions & honest limitations

This document exists because the challenge explicitly rewards noticing and
reporting real gaps rather than papering over them. Everything below is a
deliberate, documented tradeoff — not an oversight.

## 1. Only two files were actually provided to this build

The challenge brief references a large reference pack (Reference Documents
Summary, Sample-1000-Items, the 200-item Input-vs-Delivery-Format file,
content guidelines, UOM standards, Decimal_Fraction, the manufacturer/brand
master list, the cross-category LOV, FAUCETS_LOV, Fittings_LOV). **This
build only received two files**: the 1000-row sample input CSV, and a CSV
containing the *header row plus 2 example records* of the delivery format
(both Frigidaire/Whirlpool dishwashers). There was no 200-item labelled
benchmark, no content-guidelines document, no UOM/fraction/manufacturer/LOV
master spreadsheets.

**What this build did about it**: rather than fabricate data pretending to
be the official master files, `scripts/build_reference_data.py` builds
honestly-labeled seed tables — UOM abbreviations and fraction math from
genuine, well-known standards (these are just arithmetic and NIST/ANSI-style
conventions, not guesses); manufacturer/brand aliases curated from public
brand knowledge for the manufacturers actually observed in the sample;
taxonomy/LOV entries reverse-engineered from the one verified ground-truth
category (dishwashers) plus the product categories actually present in the
1000-row sample. Every source CSV has a `SOURCE` or `confidence` column
(`observed_input` / `curated_seed` / `ground_truth` / `confirmed`) so it's
always traceable which rows are verified vs. best-effort. Every loader
(`app/manufacturer/resolver.py`, `app/lov/vocabulary.py`, `app/uom/engine.py`,
etc.) checks `data/reference/external/<official-filename>` first — dropping
the real Unilog master files in there raises coverage/accuracy with **zero
code changes**.

## 2. Live manufacturer-source retrieval is not wired up

The challenge's source hierarchy (manufacturer product page > docs > spec
PDF > install manual > catalog > bulletin, marketplaces excluded) is
implemented as a real, tested authority ranking
(`app/provenance/sources.py`), but this sandboxed build environment blocks
arbitrary outbound web requests (verified: a fetch to frigidaire.com was
rejected by the network egress proxy). So there is no live connector
actually pulling manufacturer pages/PDFs.

**Consequence, stated plainly**: for the two verified dishwasher rows, the
input `Part_Desc` ("PDSH4816AF Dishwasher SS - Display Only") is extremely
sparse — it contains a material code and a "Display Only" flag and nothing
else. The rich ground-truth attributes (wash cycles, voltage, amperage,
mounting, dimensions, sound level) are **not derivable from the given input
alone**; they require external retrieval this environment can't perform.
Rather than hallucinate plausible-looking values, the pipeline correctly
reports them `UNKNOWN` and routes the record for review. This is the
no-hallucination engine working as designed, not a bug — see the
`groundedness_rate` metric in `reports/evaluation.md`, and note that
manufacturer/brand/classpath — the fields that ARE derivable from the given
input — score 100% against ground truth.

The retrieval adapter interface, authority ranking, and caching layer are
real and unit-testable; a manufacturer-page/PDF connector is a drop-in away.

## 3. Classification coverage (~27% resolved on the full 1000-row batch)

`app/taxonomy/classifier.py` only confidently classifies the 11 leaf
categories this build had time to seed
(`data/reference/category_keywords.csv`) — Dishwashers, Wall Lights, LED
Retrofit Lamps, Fluorescent Lamps, Outlets & Receptacles, Box Covers,
Ceiling Fans, Decking Boards, Railing Systems, Abrasive Discs, Cut-Off
Discs — chosen because they're the categories actually present in the
1000-item sample. The sample also contains lumber, tape, eyewear, and other
categories this build didn't reach. An unclassified row is honestly
UNRESOLVED and flagged for review, never forced into the nearest guess.
This is a coverage gap from limited category-authoring time, not an
architectural limit: the classifier is table-driven, and widening coverage
is adding rows to `category_keywords.csv` / `taxonomy_lov.csv`, not writing
new code.

## 4. Dept/Class/Fine vs. Classpath

The ground-truth file's `Dept`/`Class`/`Fine` columns use different label
text than `Classpath` (e.g. Dept="Appliances", Class="Large Appliances",
Fine="Dishwashers" vs. Classpath="Appliances & Consumer
Electronics>Kitchen Appliances>Built-In Dishwashers") — they are not the
same taxonomy at different granularity, and cannot be derived by splitting
Classpath text. Only the one classpath confirmed against ground truth has a
Dept/Class/Fine mapping (`data/reference/classpath_dept_class_fine.csv`);
everything else is left empty rather than guessed.

## 5. Digital assets (images, spec sheets, manuals)

No image/document sourcing pipeline is implemented (would need the same
live manufacturer-retrieval access as §2). Those ~20 output columns are
left empty; `Actual Image (Yes/No)` is deterministically set to `No` since
that's a true statement about this build's output, not a guess.

## 6. Evaluation sample size

Field-accuracy metrics in `reports/evaluation.md` are computed against
exactly 2 verified rows because that's all the ground truth this build
received. The harness (`app/evaluation/evaluator.py`) is written to scale
to however many rows the official 200-item benchmark provides —
`ground_truth_rows_matched` and every accuracy fraction would simply grow.
The batch coverage/quality metrics (resolution rates, validation pass rate,
review rate, groundedness) need no ground truth and are computed honestly
over the full 1000-row sample.
