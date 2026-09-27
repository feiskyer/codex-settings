# Read-only gh Command Reference

Read only when a command is needed. These examples use PR 78; substitute the actual repository, number, and captured SHAs. Publication is covered separately in [publishing.md](publishing.md).

## Read-only

```sh
# List open PRs
gh pr list

# View PR description and metadata
gh pr view 78

# View PR code changes
gh pr diff 78

# Size probe
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

# Read any file at the captured head SHA
gh api "repos/OWNER/REPO/contents/PATH?ref=HEAD_SHA" --jq '.content' | base64 -d

# Guidance files this PR modifies (report as a note, not a finding)
gh pr diff 78 --name-only | rg '(CLAUDE|AGENTS)\.md$'

# Your login (only when checking your prior review)
gh api user --jq '.login'

# Existing top-level comments, review bodies, and inline discussion
gh pr view 78 --json comments,reviews
gh api repos/OWNER/REPO/pulls/78/comments --paginate \
  --jq '.[] | {path, line, body, author: .user.login, assoc: .author_association}'

# Latest commit time (for repeat-review checks)
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

`gh pr diff` follows the live PR. Re-check the head before finalizing findings; if it moved, refresh and revalidate affected findings or explicitly report the captured snapshot and the gap. Missing/truncated patches are not evidence that a file is safe.
