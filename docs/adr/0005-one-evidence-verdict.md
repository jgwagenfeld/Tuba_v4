---
status: accepted
---

# One verdict decides evidence reuse and freshness

Evidence is reusable only when its execution attestation is intact, its trust is verified, and its solver input identity matches what the model and study would compile now. `tuba/project/evidence.py` is the one module that answers this, from an evidence folder and an expected identity; the solve's reuse decision, the solver's pre-import probe and the studio's staleness are projections of that verdict. Freshness is defined as the absence of reusability: a review reads stale when any operation's evidence is missing, damaged, unverified, or mismatched.

We chose this over keeping the studio's cheap identity-only comparison, which read a damaged or unverified folder as fresh while a solve would re-solve it, so the review the engineer was told was current could not be reused. As a consequence "stale" is at least as strict as "a solve would redo it" — the two can never disagree — and the studio's staleness check reads and hashes the same artifacts a solve would, memoized inside the verdict module by path and mtime. After import the analysis run keeps its own trust metadata as the downstream authority, so publication, reporting and review readers never need the evidence folder to outlive the run.
