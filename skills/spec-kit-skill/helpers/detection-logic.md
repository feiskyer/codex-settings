# Spec-Kit Detection Logic

Comprehensive detection algorithms for determining project state and guiding users through the spec-kit workflow.

## 1. CLI Installation Detection

Check if the `specify` CLI is installed on the system.

### Method 1: Command Check

```bash
if command -v specify &> /dev/null; then
  echo "CLI installed via PATH"
  specify --version
  exit 0
fi
```

### Method 2: Direct Path Check

```bash
if [ -x "$HOME/.local/bin/specify" ]; then
  echo "CLI installed in ~/.local/bin"
  "$HOME/.local/bin/specify" --version
  exit 0
fi
```

### Method 3: UV Tool Check

```bash
if command -v uv &> /dev/null; then
  if uv tool list | grep -q "specify-cli"; then
    echo "CLI installed via uv tool"
    uv tool run specify --version
    exit 0
  fi
fi
```

### Combined Detection Function

```bash
detect_cli() {
  # Check command
  if command -v specify &> /dev/null; then
    echo "installed"
    return 0
  fi

  # Check local bin
  if [ -x "$HOME/.local/bin/specify" ]; then
    echo "installed"
    return 0
  fi

  # Check uv tool
  if command -v uv &> /dev/null && uv tool list 2>/dev/null | grep -q "specify-cli"; then
    echo "installed"
    return 0
  fi

  echo "not_installed"
  return 1
}
```

### Installation Guidance

If CLI not detected, guide user:

```markdown
The spec-kit CLI is not installed. To install:

**Persistent installation (recommended):**
```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
```

**One-time usage:**
```bash
uvx --from git+https://github.com/github/spec-kit.git specify init .
```

**Requirements:**
- Python 3.11+
- Git
- uv package manager (install from https://docs.astral.sh/uv/)
```

## 2. Project Initialization Detection

Check if current project is initialized with spec-kit.

### Primary Indicators

```bash
check_initialization() {
  # Must have .specify directory
  if [ ! -d ".specify" ]; then
    echo "not_initialized"
    return 1
  fi

  # Must have constitution
  if [ ! -f ".specify/memory/constitution.md" ]; then
    echo "partially_initialized"
    return 2
  fi

  # Must have scripts
  if [ ! -d ".specify/scripts/bash" ]; then
    echo "partially_initialized"
    return 2
  fi

  # Must have templates
  if [ ! -d ".specify/templates" ]; then
    echo "partially_initialized"
    return 2
  fi

  echo "initialized"
  return 0
}
```

### Initialization Guidance

If not initialized:

```bash
# Initialize in current directory
specify init . --ai codex

# Initialize new project
specify init <project-name> --ai codex

# Options:
# --force: Overwrite non-empty directories
# --no-git: Skip Git initialization
# --script ps: Generate PowerShell scripts (Windows)
```

## 3. Feature Detection

Identify existing features and latest feature.

### List All Features

```bash
list_features() {
  if [ ! -d ".specify/specs" ]; then
    echo "No features found"
    return 1
  fi

  # List numbered feature directories
  ls -d .specify/specs/[0-9]* 2>/dev/null | sort -V
}
```

### Get Latest Feature

```bash
get_latest_feature() {
  LATEST=$(ls -d .specify/specs/[0-9]* 2>/dev/null | sort -V | tail -1)

  if [ -z "$LATEST" ]; then
    echo "No features found"
    return 1
  fi

  echo "$LATEST"
  return 0
}
```

### Extract Feature Name

```bash
get_feature_name() {
  FEATURE_DIR="$1"

  # Extract from directory name (e.g., 001-feature-name -> feature-name)
  basename "$FEATURE_DIR" | sed 's/^[0-9]\{3\}-//'
}
```

### Extract Feature Number

```bash
get_feature_number() {
  FEATURE_DIR="$1"

  # Extract number (e.g., 001-feature-name -> 001)
  basename "$FEATURE_DIR" | grep -o '^[0-9]\{3\}'
}
```

## 4. Phase Detection

Determine current phase of development for a feature.

### Comprehensive Phase Detection

```bash
detect_phase() {
  FEATURE_DIR="$1"

  # Phase 1: Constitution
  if [ ! -f ".specify/memory/constitution.md" ]; then
    echo "constitution"
    return 0
  fi

  # Phase 2: Specify
  if [ ! -d "$FEATURE_DIR" ] || [ ! -f "$FEATURE_DIR/spec.md" ]; then
    echo "specify"
    return 0
  fi

  # Phase 3: Clarify
  # Check if spec has clarifications section
  if ! grep -q "## Clarifications" "$FEATURE_DIR/spec.md" 2>/dev/null; then
    echo "clarify"
    return 0
  fi

  # Phase 4: Plan
  if [ ! -f "$FEATURE_DIR/plan.md" ]; then
    echo "plan"
    return 0
  fi

  # Phase 5: Tasks
  if [ ! -f "$FEATURE_DIR/tasks.md" ]; then
    echo "tasks"
    return 0
  fi

  # Phase 6/7: Analyze or Implement
  # Check if there are uncompleted tasks
  if grep -q "\\- \\[ \\]" "$FEATURE_DIR/tasks.md" 2>/dev/null; then
    echo "implement"
    return 0
  fi

  # All tasks complete
  echo "complete"
  return 0
}
```

### Phase-Specific Checks

#### Check Constitution Exists

```bash
has_constitution() {
  [ -f ".specify/memory/constitution.md" ]
}
```

#### Check Specification Exists

```bash
has_specification() {
  FEATURE_DIR="$1"
  [ -f "$FEATURE_DIR/spec.md" ]
}
```

#### Check Clarifications Present

```bash
has_clarifications() {
  FEATURE_DIR="$1"
  grep -q "## Clarifications" "$FEATURE_DIR/spec.md" 2>/dev/null
}
```

#### Check Plan Exists

```bash
has_plan() {
  FEATURE_DIR="$1"
  [ -f "$FEATURE_DIR/plan.md" ]
}
```

#### Check Tasks Exist

```bash
has_tasks() {
  FEATURE_DIR="$1"
  [ -f "$FEATURE_DIR/tasks.md" ]
}
```

#### Get Incomplete Tasks

```bash
get_incomplete_tasks() {
  FEATURE_DIR="$1"

  if [ ! -f "$FEATURE_DIR/tasks.md" ]; then
    return 1
  fi

  # Find uncompleted tasks (- [ ])
  grep -n "\\- \\[ \\]" "$FEATURE_DIR/tasks.md"
}
```

#### Get Completed Tasks Count

```bash
count_completed_tasks() {
  FEATURE_DIR="$1"

  if [ ! -f "$FEATURE_DIR/tasks.md" ]; then
    echo "0"
    return
  fi

  # Count completed tasks (- [x])
  grep -c "\\- \\[x\\]" "$FEATURE_DIR/tasks.md" 2>/dev/null || echo "0"
}
```

#### Get Total Tasks Count

```bash
count_total_tasks() {
  FEATURE_DIR="$1"

  if [ ! -f "$FEATURE_DIR/tasks.md" ]; then
    echo "0"
    return
  fi

  # Count all tasks (- [ ] or - [x])
  grep -c "\\- \\[" "$FEATURE_DIR/tasks.md" 2>/dev/null || echo "0"
}
```

## 5. Complete Status Report

Generate comprehensive status report:

```bash
generate_status_report() {
  echo "=== Spec-Kit Status Report ==="
  echo

  # CLI Status
  echo "CLI Installation:"
  CLI_STATUS=$(detect_cli)
  echo "  Status: $CLI_STATUS"
  if [ "$CLI_STATUS" = "installed" ]; then
    specify --version 2>/dev/null | sed 's/^/  /'
  fi
  echo

  # Project Status
  echo "Project Initialization:"
  INIT_STATUS=$(check_initialization)
  echo "  Status: $INIT_STATUS"
  echo

  # Constitution Status
  if has_constitution; then
    echo "Constitution: ✓ Present"
  else
    echo "Constitution: ✗ Missing (run Phase 1)"
  fi
  echo

  # Features
  echo "Features:"
  FEATURES=$(list_features)
  if [ -z "$FEATURES" ]; then
    echo "  No features found"
  else
    echo "$FEATURES" | while read -r FEATURE; do
      FEATURE_NAME=$(get_feature_name "$FEATURE")
      FEATURE_NUM=$(get_feature_number "$FEATURE")
      PHASE=$(detect_phase "$FEATURE")

      echo "  [$FEATURE_NUM] $FEATURE_NAME"
      echo "      Phase: $PHASE"

      if [ "$PHASE" = "implement" ] || [ "$PHASE" = "complete" ]; then
        COMPLETED=$(count_completed_tasks "$FEATURE")
        TOTAL=$(count_total_tasks "$FEATURE")
        echo "      Tasks: $COMPLETED/$TOTAL completed"
      fi
    done
  fi
  echo

  # Current Phase Guidance
  LATEST=$(get_latest_feature)
  if [ -n "$LATEST" ]; then
    CURRENT_PHASE=$(detect_phase "$LATEST")
    echo "Next Action: Phase $CURRENT_PHASE"
  elif has_constitution; then
    echo "Next Action: Create first feature (Phase 2: specify)"
  else
    echo "Next Action: Create constitution (Phase 1)"
  fi
}
```

## Usage Examples

### Check and Guide User

```bash
# Detect state and provide guidance
CLI_STATUS=$(detect_cli)

if [ "$CLI_STATUS" = "not_installed" ]; then
  echo "Please install spec-kit CLI first:"
  echo "uv tool install specify-cli --from git+https://github.com/github/spec-kit.git"
  exit 1
fi

INIT_STATUS=$(check_initialization)

if [ "$INIT_STATUS" != "initialized" ]; then
  echo "Please initialize project:"
  echo "specify init . --ai codex"
  exit 1
fi

# Generate status report
generate_status_report
```

### Determine Next Action

```bash
# Automatically determine what to do next
LATEST=$(get_latest_feature)

if [ -z "$LATEST" ]; then
  if has_constitution; then
    echo "Ready to create first feature"
    echo "Run: .specify/scripts/bash/create-new-feature.sh --json 'feature-name'"
  else
    echo "Need to create constitution first"
  fi
else
  PHASE=$(detect_phase "$LATEST")
  echo "Current phase: $PHASE"
  echo "Continue with phase $PHASE for feature: $(get_feature_name "$LATEST")"
fi
```
