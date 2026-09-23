---
name: code-simplifier
description: Simplify existing code for clarity and maintainability without changing behavior. Use when asked to clean up or simplify code, especially recent changes.
---

# Code Simplifier

Make code easier to understand and maintain without changing what it does. Prefer readable, explicit code over compact or clever rewrites.

## Scope and conventions

Use the user's named files or diff. Otherwise, focus on code touched in the current task or clearly identified recent changes; ask for a target if none is evident. Inspect surrounding code as needed without turning a local cleanup into a repository-wide refactor. For review-only requests, propose changes without editing.

Follow applicable project guidance, such as `AGENTS.md` or `CLAUDE.md`, and the conventions in nearby code. Derive import style, function syntax, type annotations, framework patterns, and error handling from that project rather than imposing a different style.

## Refinement criteria

- Preserve observable behavior, including public interfaces, outputs, errors, side effects, and evaluation order. Treat bug fixes or behavior changes as separate work unless requested.
- Reduce unnecessary nesting, duplication, and indirection where doing so makes the logic easier to follow. Keep helpful abstractions and separate unrelated concerns.
- Improve names and remove comments that merely restate the code; retain comments that explain intent or non-obvious constraints.
- Prefer explicit branches over nested ternaries or dense one-liners when they obscure the logic. Fewer lines alone is not an improvement.

## Completion

Finish the scoped cleanup and validate it using checks appropriate to the change and the repository's requirements. For non-obvious rewrites, check relevant edge cases against the original behavior. If behavioral equivalence remains unclear, retain the original form and explain the limitation.

Report significant refinements, checks run, and any remaining validation gaps. If no worthwhile simplification is found, say so without manufacturing edits.
