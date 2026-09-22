# CONTRACTS slice — Ruled out

**Status:** NAMED + code scaffold; product **ship claim CLOSED / DONE** by owner 2026-09-21 (SEM-ARCH-V1.4 §I.5).  
**Date:** 2026-09-21  
**Authority parent:** `docs/CONTRACTS.md`  
**Brief driver:** `docs/R3-BRIEF.md` §1 (two-axis identity; Ruled out vs Ignored)  
**Flag:** `SEMBLON_RULED_OUT` (default ON; opt out `=0`; canonical name `semblon.gates.RULED_OUT`).

This slice closes the contract gap called out in R3: Ignore alone cannot represent a durable negative identity decision.

## Verb

| Verb | Human intent | Evidence axis | Decision axis |
|---|---|---|---|
| **Ruled out** | Reject an identity hypothesis (this observation/cluster is **not** that person / not a positive ID claim) | weak or strong present | **rejected** |
| **Ignore** | Defer / leave the observation layer; do not decide identity now | any / none | **deferred** |

Ruled out is first-class: dismissed-with-rejection must not share a bit with never-considered or deferred.

## Semantics vs Ignore

| | Ruled out | Ignore (today) |
|---|---|---|
| Durable? | yes — decision row | yes — decision row |
| Meaning | human **rejected** an identity link/claim | human **deferred**; leave board / observation layer |
| Cluster row | **does not** set `clusters.status='ignored'` | sets `clusters.status='ignored'` |
| Board hide | **does not** hide by default (`hidden` not set) | face ignore sets `policy.hidden=true`; cluster leave board |
| Visual (shell, later) | dashed + `≠` / slash notch | none, ~35% opacity |
| Product wire | **ship claim CLOSED / DONE** (§I.5) | wired (`review ignore`, review-ui Ignore) |

Media stays in Library either way. Ruled out does not delete media, faces, or clusters. It does not enrol, merge, or change `compare()` / DBSCAN scores. Identity firewall unchanged: FaceKit only.

## Store mapping — **no new columns**

Reuse existing `decisions` (CONTRACTS V1.1-corrected). Same pattern as Ignore:

| Field | Value |
|---|---|
| `kind` | `reject` (existing CHECK) |
| `policy_json.action` | `"rule_out"` (Ignore uses `"ignore"`) |
| `face_id` / `cluster_id` | exactly one subject (face **or** cluster) |
| `person_id` | optional — the person identity being ruled out when known |
| `pack_id` / `run_id` / `created_at` | as other review decisions |

Example `policy_json`:

```json
{
  "action": "rule_out",
  "subject": "cluster",
  "target_person_id": null,
  "text": optional note
}
```

Re-cluster already treats any `decisions` row with `cluster_id` / `face_id` as a lock (`cluster._review_locks`). Ruled-out decisions participate without schema change.

### PROPOSED (not implemented)

Expand `decisions.kind` CHECK to include `'rule_out'` as a first-class kind. **Not required** while `action=rule_out` under `kind=reject` is distinguishable from Ignore. Do not invent columns from the brief alone. If a future slice needs a dedicated kind, land it as an explicit CONTRACTS migration with human approve — not as a silent CHECK edit.

## Code path (ship claim CLOSED / DONE)

| Surface | Behavior when flag **OFF** (`=0`) | When gate ON (default) |
|---|---|---|
| `semblon.gates.enabled(RULED_OUT)` | False | True |
| `semblon.review.rule_out_subject` | raises `ReviewError` | writes decision |
| `semblon.review_ui.apply_rule_out` | raises (via writer) | thin wrapper |
| CLI `semblon review rule-out` | exit 2 when opted out | records decision |
| review-ui / Home / shell Inspector | hidden when opted out | **Rule out** verb wired |
| `semblon.application` | exports `apply_rule_out` name; still gated | same |

Owner closed the product-wire ship claim 2026-09-21 (`SEM-ARCH-V1.4` §I.5). Opt out remains via `SEMBLON_RULED_OUT=0`.

## Historical verify notes (retained)

1. `action=rule_out` under `kind=reject` is enough (vs PROPOSED kind enum).
2. Optional `person_id` attachment for “Possible: Maya → Ruled out”.
3. Board/export should **show** Ruled out (not hide like Ignore).

See also: `docs/APPLICATION_API.md`, `docs/GATES.md`, `docs/COMPLETION-MATRIX.md`.
