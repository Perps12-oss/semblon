# Ruled out — wiring note

**Status:** product chrome **WIRED**; ship claim **CLOSED / DONE** (owner 2026-09-21, `SEM-ARCH-V1.4` §I.5)  
**Flag:** `SEMBLON_RULED_OUT` (default **ON**; opt out `=0`)  
**Contracts:** `docs/CONTRACTS-RULED-OUT.md`

Shipped surfaces:

1. review-ui **Rule out…** (`apply_rule_out` → `rule_out_subject`)
2. Home Inspector **Rule out** (`inspector_verbs` → same writer)
3. CLI `semblon review rule-out`

Ignore remains a separate deferred verb. Do not collapse the two.

Store mapping unchanged (no new columns): `decisions.kind=reject` + `policy_json.action=rule_out`.
