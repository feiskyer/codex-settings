# Publishing a GitHub Review

Read only when the user explicitly authorizes a GitHub mutation. Permission to review locally, post comments, and approve are distinct. Do not change one action into another after a failure.

## Before publication

Confirm the repository, PR number, current state, and full head SHA from live output. Do not publish a fresh review on a closed or merged PR. If the head changed, inspect the new changes and revalidate findings and coverage before publishing; an approval requires the new head to be reviewed, not just the old findings rechecked.

Preserve draft and prior-review context. Avoid duplicating a review on an unchanged head unless explicitly requested. If GitHub forbids approving your own PR, report the limitation; a fallback comment needs its own authorization.

## Placement and payload

Post findings as one batched review, not separate notifications:

- `line-anchored`: use inline comments on verified diff hunks. If the cited anchor is outside the hunk, use a relevant changed line within that same hunk; if no valid anchor exists, place the finding in the body with a code link.
- `design-level`: put the cross-file or architectural finding in the body with supporting locations.

Include every retained finding, prefix it with severity, and order by impact. Keep explanations concise but include the trigger/consequence or applicable guidance. Use `### Code review (follow-up)` for follow-ups.

Create a local JSON file using the current environment's file-editing mechanism. Replace all example values and select a non-colliding output path:

```json
{
  "commit_id": "FULL_HEAD_SHA",
  "event": "COMMENT",
  "body": "### Code review\n\nFound 2 issues (1 inline).\n\n**P1** <cross-file finding and supporting code link>",
  "comments": [
    {"path": "src/a.ts", "line": 42, "side": "RIGHT", "body": "**P1** <finding, trigger, and consequence>"}
  ]
}
```

Submit that file only after checking targets and authorization:

```sh
gh api repos/OWNER/REPO/pulls/78/reviews --method POST --input /absolute/path/to/review.json
```

Code links use the reviewed full SHA, actual repository/path, and line anchors:

```text
https://github.com/OWNER/REPO/blob/FULL_SHA/path/to/file.ext#L30-L35
```

Use nearby context only where it helps explain the defect. Never include credentials in excerpts or payloads.

## Approval and completion

Approve only when explicitly requested, required review coverage is complete, and no reportable defects remain. State the actual scope and checks; do not claim six angles, passing CI, or executed tests unless verified.

```sh
gh pr review 78 --approve --body "LGTM. <actual scope, reviewed SHA, and validation performed or skipped>"
```

Inspect the command/API result before reporting publication and return its review URL when available. After a timeout or uncertain response, check existing reviews before retrying to avoid duplicate side effects. A permission failure is a stop condition, not a reason to switch APIs.
