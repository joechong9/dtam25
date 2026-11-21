# Facts changelog

What was added to, changed in or dropped from the canonical facts
(`dtam_constants.json`, with provenance in `dtam_facts.json`), and why. Newest first.
One line per change; say who approved it. Rules: never invent a fact to fill a gap,
and never change a UREC, sample or supervisor fact without YZ.

- 2026-11-21 · added `dtam_facts.json` (source, date, owner, `confirmed_by_pi` for every
  constant), the `facts` command, `REVIEW_LOG.md` and `CONTEXT_AGENT.md`. No constant
  value changed. All `confirmed_by_pi` flags start `false`; YZ flips them.
