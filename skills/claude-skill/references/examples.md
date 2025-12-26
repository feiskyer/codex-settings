# Example Usage Scenarios

## Code Analysis (Read-Only)

**User**: "Count the lines of code in this project by language"
**Command**:

```bash
claude -p "count the total number of lines of code in this project, broken down by language" \
  --allowedTools "Read,Bash(find),Bash(wc)"
```

**Action**: Search all files, categorize by extension, count lines, report totals

## Bug Fixing

**User**: "Fix the authentication bug in the login flow"
**Command**:

```bash
claude -p "fix the authentication bug in the login flow" \
  --permission-mode acceptEdits \
  --allowedTools "Bash,Read,Write,Edit"
```

**Action**: Find the bug, implement fix, run tests

## Feature Implementation

**User**: "Implement dark mode support for the UI"
**Command**:

```bash
claude -p "add dark mode support to the UI with theme context and style updates" \
  --permission-mode acceptEdits \
  --allowedTools "Bash,Read,Write,Edit"
```

**Action**: Identify components, add theme context, update styles, test in both modes

## Batch Operations

**User**: "Update all imports from old-lib to new-lib"
**Command**:

```bash
claude -p "update all imports from old-lib to new-lib across the entire codebase" \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Edit,Bash(npm test)"
```

**Action**: Find all imports, perform replacements, verify syntax, run tests

## Generate Report with JSON Output

**User**: "Analyze security vulnerabilities and output as JSON"
**Command**:

```bash
claude -p "analyze the codebase for security vulnerabilities and provide a detailed report" \
  --allowedTools "Read,Grep" \
  --output-format json
```

**Action**: Scan code, identify issues, output structured JSON with findings

## SRE Incident Response

**User**: "Investigate the payment API errors"
**Command**:

```bash
claude -p "Incident: Payment API returning 500 errors (Severity: high)" \
  --append-system-prompt "You are an SRE expert. Diagnose the issue, assess impact, and provide immediate action items." \
  --output-format json \
  --allowedTools "Bash,Read,mcp__datadog" \
  --mcp-config monitoring-tools.json
```

**Action**: Analyze logs, identify root cause, provide action items

## Automated Security Review for PRs

**User**: "Review the current PR for security issues"
**Command**:

```bash
gh pr diff | claude -p \
  --append-system-prompt "You are a security engineer. Review this PR for vulnerabilities, insecure patterns, and compliance issues." \
  --output-format json \
  --allowedTools "Read,Grep"
```

**Action**: Analyze diff, identify security issues, output structured report

## Multi-Turn Legal Document Review

**User**: "Review multiple aspects of a contract"
**Commands**:

```bash
# Start session and capture ID
session_id=$(claude -p "start legal review session" --output-format json | jq -r '.session_id')

# Review in multiple steps
claude -r "$session_id" -p "review contract.pdf for liability clauses" \
  --permission-mode acceptEdits
claude -r "$session_id" -p "check compliance with GDPR requirements" \
  --permission-mode acceptEdits
claude -r "$session_id" -p "generate executive summary of risks" \
  --permission-mode acceptEdits
```

**Action**: Multi-turn analysis with context preservation
