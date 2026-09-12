# SEMBLON — Engineering Observatory V1

**Status:** Measurement spine. Not a North Star. Not a contract. Not a development gate.  
**Date:** 2026-09-12  
**Length limit:** stay short. If this file grows into a planning system, cut it.

```
Maturity Blueprint  →  where we are going
Contracts           →  what this stage must guarantee
Observatory         →  did what we built get better or worse?
```

Does not tell development what to build.  
Does not block experiments, 0.3 dump, or 0.4.  
Does not reopen FACE tickets or `CONTRACTS.md`.

Canonical stages (do not remap):

**S0 Born → S1 Aware → S2 Disciplined → S3 Learning → S4 Recognising → S5 Useful → S6 Remembering → S7 Temporal → S8 Conversing → S9 Mature**

---

## Rule

**The Observatory does not prevent experimentation or feature development. It prevents unexplained regression from being mistaken for progress.**

During a build:

| Situation | Allowed? |
|---|---|
| Accuracy −2%, speed +30% | Yes. Investigate. |
| New capability needs +100 MB RAM | Yes. Measure and decide. |
| Experimental clusterer is worse | Yes. That is an experiment. |

When someone says **“this stage is ready to promote”**:

then measure. No unexplained red.

---

## Loop

```
BUILD → MEASURE → COMPARE → DIAGNOSE → IMPROVE → FREEZE GOOD BASELINE → CONTINUE
```

Scavenge / absorb stays the existing Discovery habit. This file is only the measuring stick.

---

## What to measure

No composite “Semblon score.” No industrial 87%. An **evidence board** with raw numbers behind it.

| Family | Examples |
|---|---|
| Accuracy | genuine / impostor, FAR / FRR, hard negatives, lookalikes |
| Recognition | top-1, top-2 margin, unknown rejection |
| Clustering | impurity, worst intra-cluster pair |
| Detection | recall by face-size / quality band |
| Speed | time-to-first-result, throughput, stage latency, cold start |
| Resources | peak RSS, CPU / GPU / NPU, model load |
| User effort | review decisions, corrections / 1k faces, time-to-useful-result |

Stratify accuracy when the set supports it (size, pose, quality, source). Averages hide disasters.

User effort matters as much as headline precision: fewer honest reviews can beat a prettier FAR.

Print precision **only** on frozen confirmatory sets (`CONTRACTS.md`). Underpowered → say so, don’t invent a number.

---

## Three references (not interchangeable)

**A. Semblon golden baseline** — the known-good *our* build. Most important. Catches “we got worse.”

Record with the run:

```
commit / pack_id / config / corpus / hardware / arch / execution (native|emulated)
```

**B. External / reference** — what credible systems do on a *comparable* task. Useful for “we are embarrassingly slow.” Not an automatic pass/fail; hardware, models, datasets, and objectives differ.

**C. Maturity threshold** — what *we* require before calling a stage done. This is the promotion criterion, not B.

Keep corpora distinct: development · frozen regression · confirmatory eval · hard-negative tray · real dump. Do not optimise the test. Mined tail is discovery; remine does not refresh confirmatory.

---

## When it actually runs

| Moment | Observatory |
|---|---|
| Normal development | Optional. Log if cheap. |
| Meaningful infra change (pack, clusterer, runtime) | Compare to golden. |
| Stage promotion (S*n* → S*n+1*) | Required. Evidence board + known regressions. |
| Current 0.3 dump / 0.4 CLI | **Not a gate.** Open the page; ship the CLI. |

Promotion verdicts:

| Mark | Meaning |
|---|---|
| Improvement | Better on the thing the stage exists for, no unexplained red |
| Trade-off | Mixed; accepted in writing |
| Regression | Unexplained red → not mature yet |
| Not measurable | Insufficient evidence; do not fake it |

FACE-002 is the first accuracy slice of this spine, not a second bureaucracy.

---

## Golden freeze (example shape)

```
baseline:
  commit / pack_id / config / corpus / hardware / native|emulated
accuracy:   ...     (confirmatory only)
speed:      first result / throughput / stage times
resources:  peak RSS
effort:     review count / corrections per 1k
regressions: none | listed and accepted
```

Git history should read like: *feature X — accuracy unchanged, throughput +14%, RSS +4%* — not only *feature X added*.

---

## Do not

- Merge this into the Maturity Blueprint  
- Gate everyday tickets on a dashboard  
- Publish one aggregate industrial number  
- Chase donor FPS or donor FAR as Semblon’s pass mark  
- Add a research register / tech radar / ADRs for this  
- Remap S2–S8 to Review / Search / Video  

If a future sentence cannot be said in this file without a new planning doc, the sentence is wrong.

---

*Capabilities become mature when they have been shown accurate, fast enough, cheap enough, and useful — not when the feature list got longer.*
