# Demo script (~4 minutes)

## 1. Cold open — the problem (20s)

Show a raw row: `PDSH4816AF Dishwasher SS - Display Only`. That's the
entire input. Ask: "what's the manufacturer? Frigidaire isn't even in the
text." → sets up why naive LLM prompting fails here (nothing to ground it
in) and why this needed a pipeline, not a prompt.

## 2. Live single-record enrichment (60s)

Open **Product Enrichment**. Click the "Dishwasher (Frigidaire, verified)"
example. Narrate the flow strip as it lights up: Clean → Entity Resolution
→ Classify → Extract → Normalize → Validate → Score → Review?.

Point at the evidence panel: *"MPN prefix 'PDSH' matched a confirmed
manufacturer pattern"* — the system didn't guess Frigidaire, it resolved it
against master data and cites exactly why, even flagging that the
Part_Manuf field ("Appliance Dealers Cooperative") is a distributor, not
the true OEM, and correctly ignored it in favor of stronger evidence.

Switch to the Cut-off Disc example — show grit/diameter/thickness pulled
directly out of the text with DIRECT provenance, then promoted to
NORMALIZED with trade-fraction formatting (`7/8 in`, not `0.875`).

## 3. Batch scale (60s)

Go to **Batch Upload**, upload `sample_1000_items_input.csv`. Watch it
process 1000 rows in ~1 second. Land on **Dashboard**: real counts, real
confidence, real review rate — not a canned number.

## 4. The honesty differentiator (45s)

Open **Review Queue**. This is the pitch: *"771 records got flagged, and
here's exactly why — uncertain classification, low confidence — with
per-record reasons a human can act on in seconds. We're not showing you a
99%-accuracy demo hiding failures; we're showing you a system that knows
what it doesn't know."*

Open one flagged record, show the reasons and evidence trail.

## 5. Evaluation (30s)

Open **Evaluation**, click Run. Show 100% field accuracy on the verified
ground-truth rows (manufacturer, brand, classpath) and the honest coverage
numbers on the full batch. Say plainly: *"We only received 2 verified
ground-truth rows in this challenge's resources — this harness scales to
however many the judges' evaluation set provides, unchanged."*

## 6. Download + close (25s)

Download XLSX from the Batch Upload view, open it, scroll to column IV —
all 252 official headers present, exactly spelled, nothing dropped. Close
on the differentiator line: *"We don't ask the LLM to invent product
content — we built a constrained product-intelligence compiler: master
data, retrieval, reasoning, normalization, evidence, and validation,
working together."*

## Fallback if the network/API is down

Everything above runs in `APP_MODE=mock` — the default — with zero
external calls. The entire demo is reproducible offline.
