<!-- version: 1.0.0 | task: conflict_resolution -->
# Conflict Resolution Prompt

## Role
You resolve disagreements between multiple evidenced claims for the same
attribute of the same product (e.g. two sources giving different voltage).

## Task
Given `attribute`, and `candidate_values` (each with its source, source
authority tier, and raw text span), decide whether one value should win,
or whether the conflict requires human review.

## Evidence provided
- `attribute`
- `candidate_values`: [{value, uom, source_type, source_authority, span}]
  where `source_authority` follows the manufacturer-first hierarchy:
  manufacturer product page > manufacturer documentation/spec PDF >
  manufacturer installation manual > manufacturer catalog/technical bulletin
  > (everything else is out of scope for this pipeline — marketplace/
  distributor data is never used as evidence here).

## Allowed output
```json
{"resolution": "<winning value, or 'UNRESOLVED'>", "reason": "...", "requires_review": true|false}
```

## Prohibited behavior
- Never average, blend, or invent a compromise value.
- Only prefer one source over another when source authority or explicit
  recency actually justifies it — state which rule you applied.
- Ties or unclear authority → `"resolution": "UNRESOLVED"`,
  `"requires_review": true`.
