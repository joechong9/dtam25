# Proposed patches to the account-level `dtam-*` skills

The skills are synced from the claude.ai account, so a repository session cannot
edit them. Apply these in the skill editor (or with the `skill-creator` skill). They
finish recommendation 3 (one source of truth) and the portability fix.

## Audit result (2026-11-05)

`python3 harness/dtam_harness.py check --external <skills>/dtam-*/SKILL.md` found
**no numeric drift**: every skill agrees with `harness/dtam_constants.json`. The only
hits are lines that document the forbidden strings themselves, which are expected
named exceptions. The risk is not drift today but duplication: the same constants
are restated in 12 skills, CLAUDE.md (PostGrad Work), and 3 library-app copies.

## Patch 1: replace the restated constants in every §0 guardrail block

In each of the 11 skills that carry `## §0 Guardrails`, replace item 4:

```diff
-4. CONSTANTS: Total n=370; pilot n=70 (42 urban + 28 rural, 45 completers); GCP 19/22; A/Prof Dr Kwan Ban Hoe (main) · A/Prof. Ir. Dr Goh Choon Hian (co) · LKC FES.
+4. CONSTANTS: take every number and name from `dtam_constants.json` (repo: harness/; PostGrad Work: same file) — never from memory or another skill. If that file is unavailable, use CLAUDE.md §1. Run the harness `check` before delivering.
```

Keep the §0 block itself. Its duplication is intentional, because it makes each
skill safe when loaded alone. Only the numbers move out.

Apply the same change to `dtam-working-method` §1.1, §3.3 and §5, and to the
"Canonical constants" footer of `dtam-loop-engine`.

## Patch 2: one drift-rule source for the Loop Engine and library apps

`dtam-library-apps` says the validation core is "duplicated across three files and
must change in all three". Point all three at `drift_rules.json` instead:

- Bundle Compiler (Python): load `drift_rules.json` at start-up instead of the
  inline `FORBIDDEN_RULES` list. The patterns are already Python-compatible.
- Report Assembler and Citation Auditor (HTML): add the
  `/* DTAM_RULES:BEGIN */ /* DTAM_RULES:END */` markers and let
  `dtam_harness.py sync --write` fill them, as `admin_portal_v2.html` now does.
- Loop Engine: register a verifier that shells out to
  `dtam_harness.py check --json FILES` and maps `new` findings to LES findings.

Then edit the skill's "Extension recipes" to read: *add the rule to
drift_rules.json, add fixtures to harness/tests, run sync --write*.

## Patch 3: portability (Cowork/macOS-only assumptions)

| Skill | Line | Change |
|---|---|---|
| `dtam-council` | "Canonical file: /Users/yuchong/Documents/..." | Express it relative to the project root (`PostGrad Work/council_of_advisors.html`) and resolve it through `dtam_manifest.json`. |
| `dtam-council` | "After every edit: call mcp__cowork__update_artifact" | Add: "only in Cowork; in Claude Code, publish with the Artifact tool or skip." |
| `dtam-council` | `window.cowork.askClaude` "is the only CDN-free LLM path" | Add the proxy path (`proxy/claude-proxy-worker.js`) as the non-Cowork option. |
| `dtam-manual-compiler`, `dtam-doc-formatter` | "PostGrad Work is the default" | State the fallback when the folder is absent (repository root), so cloud sessions do not silently write elsewhere. |

## Patch 4: wire the harness into `dtam-working-method` §7

Add a final checklist item:

```diff
+11. Did `python3 harness/dtam_harness.py check` report 0 new findings? If the
+    PostToolUse hook blocked an edit, did I fix the cause at source instead of
+    working around it?
```

## Patch 5: architecture-doc agent count

`dtam-architecture-doc` says "Specialist agent layer — 8 agents" but lists 7
(Ethics & Protocol, Questionnaire & OMR, Literature & Framework, Statistical &
Analytics, App & FHIR Dev, QA & Data Warehouse, ML Pipeline). Either name the eighth
or change the count to 7. This needs your decision.
