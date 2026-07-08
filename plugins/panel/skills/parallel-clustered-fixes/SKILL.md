---
name: parallel-clustered-fixes
description: Use this in the /panel triage→fix stage AFTER blocker-triage has produced the confirmed fix list and BEFORE you start editing. When a PR comes back with many confirmed findings that partition into DISJOINT file-clusters, fan the fixes out — one worktree-isolated agent per cluster — instead of one sequential agent. Gates the fan-out on a heuristic so small or overlapping work stays serial, and re-runs the combined gate (tests + bin/tdd-check) after merging the worktrees back.
---

# Parallel Clustered Fixes — fan out only when it actually saves wall-clock

You have a triaged list of REAL fixes (from `blocker-triage`). The default is to
fix them with one sequential agent. Fan out ONLY when the work genuinely
partitions; parallelism has real merge/coordination overhead and is a net loss on
small or entangled fixes.

## Decision: fan out or stay serial?

Fan out **only when BOTH hold**:

1. **Numerous** — there are enough confirmed fixes that serial wall-clock hurts.
   Rule of thumb: **≥ 4 confirmed fixes**. Fewer than that, stay serial.
2. **Disjoint** — the fixes partition into **≥ 2 clusters that share no files**.
   If every fix collapses into one big cluster, there is nothing to parallelize.

Stay **serial** (the default) when ANY of these is true — do not fan out:

- **Overlap** — two findings edit the same file. Parallel agents on a shared file
  clobber each other; worktrees don't help because the merge conflicts.
- **Small** — a handful of one-line fixes. The worktree setup + merge + combined
  gate costs more than it saves.
- **Tightly coupled** — fixes that must be reconciled together (a signature change
  and all its call sites, an interface and its implementors). Split across agents,
  each sees half the picture.

> **M3 dogfood counter-example (kept serial, correctly):** findings R1–R5 were
> small and several shared `backfill.rs`. Overlap + small ⇒ serial. This skill
> must reproduce that verdict: presented R1–R5, it does NOT fan out.

## Step 1 — build the file→cluster partition

From the triaged fix list, map **each confirmed finding to the file(s) it will
touch** — and when you map, include **indirect edits**: shared registration /
manifest files that the fix will necessarily also modify (Rust `mod.rs`/`lib.rs`,
`package.json`, `__init__.py`, lockfiles). Two findings that both touch such a file
overlap even if their *source* files differ. Then compute connected components: two
findings are in the same cluster if they share ANY file (transitively). This is a
union-find over findings keyed by file path.

Present the partition before doing anything (the `Cluster` id — `A`, `B`, ... — is
what the per-cluster agent in Step 2 is labelled with):

| Cluster | Findings | Files (disjoint across clusters, incl. manifests) |
|---------|----------|---------------------------------------------------|
| A | R2, R6 | `src/store/iv_store.rs`, `src/store/mod.rs` |
| B | R4 | `src/api/handlers.rs` |
| C | R7, R8 | `src/render/chart.tsx`, `src/render/legend.tsx` |

If the table has one row → serial. If a file appears in two rows, your partition is
wrong — those findings belong to the same cluster (that's overlap ⇒ likely serial).

## Step 2 — one worktree-isolated agent per cluster

Fan the clusters out with the SAME parallel/worktree mechanism panel already uses in
step 3 of the loop — superpowers' `using-git-worktrees` + `dispatching-parallel-agents`
(or, equivalently, the Workflow tool with `isolation: 'worktree'`). One agent per
cluster, each in its own git worktree. Worktree isolation is what makes parallel
file-editing safe — without it, agents share one working tree and clobber each
other's edits. Do not introduce a second vocabulary for this; use whichever of the
two the surrounding loop already invoked.

Each cluster agent:

- Fixes **only its cluster's findings**, touching **only its cluster's files**.
- Follows the **same two-commit TDD cadence** panel enforces everywhere: a `test:`
  commit that pins the fixed behavior FIRST, then the `feat:`/`fix:` commit that
  makes it pass — the `test:` commit an ancestor of the impl commit.
- Is an implementer, not a reviewer (the `implementer ≠ reviewer` invariant holds —
  these fresh fix agents did not review the PR).

Sketch in the Workflow-tool form (the `dispatching-parallel-agents` form is the
equivalent — adapt to whichever the loop is using, and to the actual clusters):

```
const clusters = [ /* from the partition table */ ];
await parallel(clusters.map(c => () =>
  agent(
    `Fix ONLY findings ${c.findings} in files ${c.files}. ` +
    `Two-commit TDD: a failing test: commit first, then the fix. ` +
    `Touch no file outside ${c.files}.`,
    { isolation: 'worktree', label: `fix:${c.id}` }
  )
));
```

## Step 3 — merge back and re-run the COMBINED gate

Because Step 1 already folded shared manifests into the overlap check, the clusters
are truly file-disjoint and merging their commits onto the feature branch should not
conflict. Bring each worktree's `test:`→`impl:` commits back onto the branch with
`git cherry-pick` (or rebase the cluster branch onto the feature branch), preserving
each cluster's `test:`-before-`impl:` ancestry.

**If a merge conflict occurs, stop — fail closed.** A conflict means the partition
was wrong (an indirect/manifest file was missed and two clusters were not actually
disjoint). Do not force the merge. Report it, fold the conflicting clusters into one,
and re-fix them serially.

Then, on the combined branch, **re-run the full gate — this is non-negotiable**:

1. The repo's own test suite (discover it from AGENTS.md / CI config).
2. `bin/tdd-check` against the branch.

**Both must be green.** Fanning out can interleave commits in a way that breaks
`test:`→`impl:` ancestry or bundles a test with impl across the merge; if
`tdd-check` goes red, fix the history (re-order / re-split) before proceeding. A red
combined gate blocks — it is not a suggestion. Never trust a cluster agent's claim
that its own gate passed; verify the combined branch independently.

## Guardrails

- **Never fan out overlapping files.** Shared-file findings are the one case where
  parallelism is unsafe regardless of worktrees — keep them in one cluster, fixed
  serially by one agent.
- **The two-commit TDD cadence holds per cluster**, and the final combined branch
  must pass `bin/tdd-check`. Parallelism changes the wall-clock, never the gate.
- **When in doubt, stay serial.** Serial is always correct; fan-out is an
  optimization you justify with the partition table, not a default.
