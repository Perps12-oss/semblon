# Architecture

**Operating model — frozen 2026-09-12.** Do not reopen.

| Doc | Job |
|---|---|
| `docs/PRODUCT.md` | what the current user can actually do (v1 frozen) |
| `docs/CONTRACTS.md` | what the implementation must guarantee |
| `docs/SEMBLON_MATURITY_BLUEPRINT.md` | what Semblon can eventually become (S0–S9) |
| `docs/SEMBLON_CAPABILITY_DISCOVERY_BLUEPRINT.md` | scavenge useful behaviour (not install every donor) |
| `docs/SEMBLON_ENGINEERING_OBSERVATORY.md` | did this build get better? Not a development gate |

```
BUILD → SCAVENGE → MEASURE → KEEP/ADAPT/DEFER/REJECT → GOLDEN (if justified) → PROMOTE → NEXT STAGE
```

`review.html` is evidence. Use it to decide whether DBSCAN survives; it does not automatically kill an algorithm.

Observatory answers “did S3→S4 actually get better?”, not “may we experiment today?”

Do not remap stage names. Do not start a GUI because S8 exists on paper.

Current engineering: 0.3 on `main` (S1). Immediate action: real dump → ingest → cluster → review.html → look → optional S1 golden. Then 0.4.
