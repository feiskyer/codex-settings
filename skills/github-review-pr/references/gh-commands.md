# gh Command Reference

Recipes for the review workflow in SKILL.md. Read this when a step needs a command, not up front.

## Read-only

```sh
# List open PRs
gh pr list

# View PR description and metadata
gh pr view 78

# View PR code changes
gh pr diff 78

# Size probe (step 2)
gh pr view 78 --json changedFiles,additions,deletions

# File manifest for very large PRs, plus one file's patch on demand.
# GitHub omits `patch` for very large files and lists at most 3000 files.
gh api repos/OWNER/REPO/pulls/78/files --paginate --jq '.[] | {filename, additions, deletions}'
gh api repos/OWNER/REPO/pulls/78/files --paginate --jq '.[] | select(.filename == "PATH") | .patch'

# Get repo owner/name
gh repo view --json nameWithOwner --jq '.nameWithOwner'

# Get PR head and base commit SHAs (full 40-char). Reviewers read project
# guidance at the base SHA so the PR cannot rewrite the rules it is judged by.
gh api repos/OWNER/REPO/pulls/78 --jq '.head.sha'
gh api repos/OWNER/REPO/pulls/78 --jq '.base.sha'

# Read an AGENTS.md file at the base SHA (agent #1 reads each guidance file this way)
gh api "repos/OWNER/REPO/contents/AGENTS.md?ref=BASE_SHA" --jq '.content' | base64 -d

# Read any file at the head SHA (the skeptic in step 4 needs context beyond the diff)
gh api "repos/OWNER/REPO/contents/PATH?ref=HEAD_SHA" --jq '.content' | base64 -d

# Guidance files this PR modifies (report as a note, not a finding)
gh pr diff 78 --name-only | grep -E '(CLAUDE|AGENTS)\.md$'

# Your login (for the "already reviewed" check in steps 1 and 6)
gh api user --jq '.login'

# Existing top-level comments and reviews on this PR
gh pr view 78 --json comments,reviews

# Latest commit time on the PR (steps 1 and 6)
gh pr view 78 --json commits --jq '.commits[-1].committedDate'

# PRs that previously touched a file (agent #4).
# Note: walks the default branch only; does not follow renames. Exclude the current PR number.
gh api "repos/OWNER/REPO/commits?path=path/to/file&per_page=10" --jq '.[].sha' | head -5 \
  | xargs -I{} gh api repos/OWNER/REPO/commits/{}/pulls --jq '.[].number' | sort -un

# Feedback left on a past PR. Keep every comment regardless of author — other
# reviewers, bots, and the author's own replies are all useful context — but carry
# author and author_association through so weight can be judged downstream.
gh api repos/OWNER/REPO/pulls/72/comments --paginate \
  --jq '.[] | {path, line, body, author: .user.login, assoc: .author_association}'   # inline review comments
gh api repos/OWNER/REPO/issues/72/comments --paginate \
  --jq '.[] | {body, author: .user.login, assoc: .author_association}'               # top-level comments
```

## Mutations — only with explicit user authorization

```sh
# Approval. State the review's scope so a bare "LGTM" is not read as a claim
# that the change was exercised. Use "LGTM (follow-up)" for a follow-up review.
gh pr review 78 --approve --body "LGTM

<sub>Static review of the diff across 6 angles (project guidance, bugs, git history, past PR feedback, code comments, security). Build and tests were not run as part of this review.</sub>"

# Post one batched review: scope=line-anchored findings as inline comments
# anchored to diff lines, scope=design-level findings in the body. Never post
# findings via `gh pr comment`. commit_id is the full head SHA.
cat > /tmp/review.json <<'EOF'
{
  "commit_id": "FULL_HEAD_SHA",
  "event": "COMMENT",
  "body": "### Code review\n\nFound 3 issues (2 inline).\n\n1. **P0** <design-level issue> (AGENTS.md says \"<quote>\")\n\nhttps://github.com/OWNER/REPO/blob/FULL_SHA/path/to/file.ts#L30-L35",
  "comments": [
    {"path": "src/a.ts", "line": 42, "side": "RIGHT", "body": "**P0** <finding 1>"},
    {"path": "src/b.ts", "start_line": 10, "start_side": "RIGHT", "line": 14, "side": "RIGHT", "body": "**P1** <finding 2>"}
  ]
}
EOF
gh api repos/OWNER/REPO/pulls/78/reviews --method POST --input /tmp/review.json
```

## Output formats

### Review body

Use the heading `### Code review (follow-up)` for a follow-up review of new commits.

```markdown
### Code review

Found 3 issues (2 inline).

1. **P0** <design-level finding, or one whose anchor was verified to fall outside every diff hunk> (AGENTS.md says "<quote>")

https://github.com/OWNER/REPO/blob/FULL_SHA/path/to/file.ts#L30-L35

<sub>- If this code review was useful, please react with a thumbs up. Otherwise, react with a thumbs down.</sub>
```

### Inline comment

```markdown
**P1** <brief description> (project guidance says "<quote>" | bug: when X, Y happens because Z)
```

### Code link

Markdown rendering only works with this exact format:

```
https://github.com/OWNER/REPO/blob/FULL_SHA/path/to/file.ext#L[start]-L[end]
```

- Full 40-character git SHA, written out literally (no `$(git rev-parse HEAD)` — the comment renders as Markdown)
- Repo name must match the repo being reviewed
- `#` after the file name
- Line range as `L[start]-L[end]`
- Include at least 1 line of context before/after (commenting on lines 5-6 links `L4-L7`)
