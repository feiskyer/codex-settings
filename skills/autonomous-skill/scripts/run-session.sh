#!/bin/bash
#
# Autonomous Skill - Session Runner
# Executes Codex in non-interactive mode with auto-continuation
#
# Usage:
#   ./run-session.sh "task description"
#   ./run-session.sh --task-name <name> --continue
#   ./run-session.sh --list
#   ./run-session.sh --help
#

set -euo pipefail

# Configuration
AUTO_CONTINUE_DELAY=3
CURRENT_TASK_NAME=""

# Use CODEX_PLUGIN_ROOT or fallback to script directory
if [ -n "${CODEX_PLUGIN_ROOT:-}" ]; then
    SKILL_DIR="${CODEX_PLUGIN_ROOT}/skills/autonomous-skill"
else
    SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

# Task directory base (in project root)
AUTONOMOUS_DIR=".autonomous"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Print colored output
print_header() {
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}==========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Handle Ctrl+C gracefully
handle_interrupt() {
    echo ""
    if [ -n "${CURRENT_TASK_NAME:-}" ]; then
        print_warning "Interrupted. Progress saved in $AUTONOMOUS_DIR/$CURRENT_TASK_NAME/"
        echo "Run again to continue: $0 --task-name $CURRENT_TASK_NAME --continue"
    else
        print_warning "Interrupted."
    fi
    exit 130
}

# Show help
show_help() {
    echo "Autonomous Skill - Session Runner (Codex)"
    echo ""
    echo "Usage:"
    echo "  $0 \"task description\"           Start new task (auto-generates name)"
    echo "  $0 --task-name <name> --continue Continue specific task"
    echo "  $0 --list                        List all tasks"
    echo "  $0 --help                        Show this help"
    echo ""
    echo "Options:"
    echo "  --task-name <name>       Specify task name explicitly"
    echo "  --continue, -c           Continue existing task"
    echo "  --no-auto-continue       Don't auto-continue after session"
    echo "  --max-sessions N         Limit to N sessions"
    echo "  --list                   List all existing tasks"
    echo "  --resume-last            Resume the most recent Codex session"
    echo "  --network                Enable network access (uses danger-full-access sandbox)"
    echo ""
    echo "Examples:"
    echo "  $0 \"Build a REST API for todo app\""
    echo "  $0 --task-name build-rest-api --continue"
    echo "  $0 --task-name build-rest-api --continue --resume-last"
    echo "  $0 --list"
    echo ""
    echo "Task Directory: $AUTONOMOUS_DIR/<task-name>/"
    echo "Skill Directory: $SKILL_DIR"
    echo ""
}

# Generate task name from description
generate_task_name() {
    local desc="${1:-}"
    # Convert to lowercase, replace non-alphanumeric with hyphens, collapse multiple hyphens, trim
    local result
    result=$(echo "$desc" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | cut -c1-30 | sed 's/^-//' | sed 's/-$//')

    # If result is empty (description was non-ASCII or only special chars), use timestamp fallback
    if [ -z "$result" ]; then
        result="task-$(date +%Y%m%d-%H%M%S)"
        print_warning "Non-alphanumeric description detected, using generated name: $result"
    fi
    echo "$result"
}

# Validate task name (security: prevent path traversal)
validate_task_name() {
    local name="$1"
    # Reject if contains path traversal attempts or invalid characters
    if [[ "$name" == *".."* ]] || [[ "$name" == *"/"* ]] || [[ "$name" == *"\\"* ]]; then
        print_error "Invalid task name: '$name' (contains path traversal characters)"
        return 1
    fi
    # Reject if empty
    if [ -z "$name" ]; then
        print_error "Task name cannot be empty"
        return 1
    fi
    # Reject if starts with hyphen (could be confused with options)
    if [[ "$name" == -* ]]; then
        print_error "Task name cannot start with a hyphen"
        return 1
    fi
    return 0
}

# Verify required commands exist
check_dependencies() {
    if ! command -v codex &> /dev/null; then
        print_error "Required command 'codex' not found"
        echo "Please install Codex CLI: https://github.com/openai/codex"
        exit 1
    fi
}

# List all tasks
list_tasks() {
    print_header "AUTONOMOUS TASKS"

    if [ ! -d "$AUTONOMOUS_DIR" ]; then
        print_warning "No tasks found. Directory $AUTONOMOUS_DIR does not exist."
        echo ""
        return
    fi

    # Check if directory is empty (no subdirectories)
    local dir_count
    dir_count=$(find "$AUTONOMOUS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    if [ "$dir_count" -eq 0 ]; then
        print_warning "No tasks found in $AUTONOMOUS_DIR/"
        echo ""
        return
    fi

    local found=0
    for task_dir in "$AUTONOMOUS_DIR"/*/; do
        # Skip if glob didn't match (empty directory case)
        [ -d "$task_dir" ] || continue

        local task_name
        task_name=$(basename "$task_dir")
        local task_list="$task_dir/task_list.md"

        if [ -f "$task_list" ]; then
            local total
            local done_count
            total=$(grep -c '^\- \[' "$task_list" 2>/dev/null | tr -d '\n' || echo "0")
            done_count=$(grep -c '^\- \[x\]' "$task_list" 2>/dev/null | tr -d '\n' || echo "0")
            # Ensure we have valid numbers
            total=${total:-0}
            done_count=${done_count:-0}

            # Safe percent calculation (avoid divide by zero)
            local percent=0
            if [ "$total" -gt 0 ]; then
                percent=$((done_count * 100 / total))
            fi

            # Check for session ID
            local session_info=""
            if [ -f "$task_dir/session.id" ]; then
                local sid
                sid=$(cat "$task_dir/session.id" | head -c 8)
                session_info=" [session: ${sid}...]"
            fi

            if [ "$done_count" -eq "$total" ] && [ "$total" -gt 0 ]; then
                echo -e "  ${GREEN}✓${NC} $task_name ($done_count/$total - 100% complete)$session_info"
            else
                echo -e "  ${YELLOW}○${NC} $task_name ($done_count/$total - $percent%)$session_info"
            fi
            found=$((found + 1))
        else
            echo -e "  ${RED}?${NC} $task_name (no task_list.md)"
            found=$((found + 1))
        fi
    done

    if [ "$found" -eq 0 ]; then
        print_warning "No valid tasks found in $AUTONOMOUS_DIR/"
    fi

    echo ""
}

# Check if task exists
task_exists() {
    local task_name="$1"
    [ -f "$AUTONOMOUS_DIR/$task_name/task_list.md" ]
}

# Get task directory
get_task_dir() {
    local task_name="$1"
    echo "$AUTONOMOUS_DIR/$task_name"
}

# Get progress from task_list.md
get_progress() {
    local task_dir="$1"
    if [ -f "$task_dir/task_list.md" ]; then
        local total
        local done
        total=$(grep -c '^\- \[' "$task_dir/task_list.md" 2>/dev/null | tr -d '\n' || echo "0")
        done=$(grep -c '^\- \[x\]' "$task_dir/task_list.md" 2>/dev/null | tr -d '\n' || echo "0")
        # Ensure we have valid numbers
        total=${total:-0}
        done=${done:-0}
        echo "$done/$total"
    else
        echo "0/0"
    fi
}

# Check if all tasks are complete
is_complete() {
    local task_dir="$1"
    if [ -f "$task_dir/task_list.md" ]; then
        local total
        local done
        total=$(grep -c '^\- \[' "$task_dir/task_list.md" 2>/dev/null | tr -d '\n' || echo "0")
        done=$(grep -c '^\- \[x\]' "$task_dir/task_list.md" 2>/dev/null | tr -d '\n' || echo "0")
        # Ensure we have valid numbers
        total=${total:-0}
        done=${done:-0}
        if [ "$done" -eq "$total" ] && [ "$total" -gt 0 ]; then
            return 0  # complete
        fi
    fi
    return 1  # not complete
}

# Extract session ID from JSON Lines output
extract_session_id() {
    local log_file="$1"
    # Prefer thread_id from thread.started; fall back to any thread_id or session_id
    local id=""
    id=$(grep -m 1 '"type":"thread.started"' "$log_file" 2>/dev/null | sed -n 's/.*"thread_id":"\([^"]*\)".*/\1/p')
    if [ -z "$id" ]; then
        id=$(grep -m 1 '"thread_id"' "$log_file" 2>/dev/null | sed -n 's/.*"thread_id":"\([^"]*\)".*/\1/p')
    fi
    if [ -z "$id" ]; then
        id=$(grep -m 1 '"session_id"' "$log_file" 2>/dev/null | sed -n 's/.*"session_id":"\([^"]*\)".*/\1/p')
    fi
    echo "$id"
}

# Run initializer session
run_initializer() {
    local task_name="$1"
    local task_desc="$2"
    local enable_network="$3"
    local task_dir=$(get_task_dir "$task_name")

    print_header "INITIALIZER SESSION"
    echo "Task: $task_desc"
    echo "Task Name: $task_name"
    echo "Task Directory: $task_dir"
    echo ""

    # Create task directory
    mkdir -p "$task_dir"

    # Read initializer prompt template and substitute {TASK_DIR} placeholder
    local init_prompt=$(cat "$SKILL_DIR/templates/initializer-prompt.md" | sed "s|{TASK_DIR}|$task_dir|g")

    # Build codex command
    # --full-auto: autonomous execution with workspace-write sandbox
    # --skip-git-repo-check: allow running outside a git repo (common for skill validation)
    local codex_cmd="codex exec --skip-git-repo-check --full-auto --json"
    if [ "$enable_network" = true ]; then
        codex_cmd="codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox --json"
    fi

    # Execute Codex in non-interactive mode
    $codex_cmd "Task: $task_desc
Task Name: $task_name
Task Directory: $task_dir

You are the Initializer Agent. Create task_list.md and progress.md in the $task_dir directory. All task files must be created in $task_dir/, not in the current directory.

$init_prompt" 2>&1 | tee "$task_dir/session.log"

    # Extract and save session ID for potential resumption
    local session_id
    session_id=$(extract_session_id "$task_dir/session.log")
    if [ -n "$session_id" ]; then
        echo "$session_id" > "$task_dir/session.id"
        print_info "Session ID saved: $session_id"
    fi

    echo ""
    print_success "Initializer session complete"
}

# Run executor session
run_executor() {
    local task_name="$1"
    local resume_last="$2"
    local enable_network="$3"
    local task_dir=$(get_task_dir "$task_name")

    print_header "EXECUTOR SESSION"
    echo "Task Name: $task_name"
    echo "Task Directory: $task_dir"
    echo ""

    # Read current state
    local task_list=$(cat "$task_dir/task_list.md" 2>/dev/null || echo "No task list found")
    local progress_notes=$(cat "$task_dir/progress.md" 2>/dev/null || echo "No progress notes yet")

    # Read executor prompt template and substitute {TASK_DIR} placeholder
    local exec_prompt=$(cat "$SKILL_DIR/templates/executor-prompt.md" | sed "s|{TASK_DIR}|$task_dir|g")

    # Build base codex command options
    # --full-auto: autonomous execution with workspace-write sandbox
    # --skip-git-repo-check: allow running outside a git repo
    local codex_opts="--skip-git-repo-check --full-auto --json"
    if [ "$enable_network" = true ]; then
        codex_opts="--skip-git-repo-check --dangerously-bypass-approvals-and-sandbox --json"
    fi

    # Build the prompt
    local prompt="Continue working on the task.
Task Name: $task_name
Task Directory: $task_dir

You are the Executor Agent. Complete tasks and update files in the $task_dir directory. All task files are in $task_dir/, not in the current directory.

Current task_list.md:
$task_list

Previous progress notes:
$progress_notes

$exec_prompt"

    # Check if we should resume the previous session
    if [ "$resume_last" = true ] && [ -f "$task_dir/session.id" ]; then
        local session_id
        session_id=$(cat "$task_dir/session.id")
        print_info "Resuming session: $session_id"

        # Resume the previous session with new instructions
        codex exec $codex_opts resume "$session_id" "$prompt" 2>&1 | tee -a "$task_dir/session.log"
    else
        # Start a new session
        codex exec $codex_opts "$prompt" 2>&1 | tee "$task_dir/session.log"

        # Save session ID
        local session_id
        session_id=$(extract_session_id "$task_dir/session.log")
        if [ -n "$session_id" ]; then
            echo "$session_id" > "$task_dir/session.id"
            print_info "Session ID saved: $session_id"
        fi
    fi

    echo ""
    print_success "Executor session complete"
}

# Main execution loop
main() {
    local task_desc=""
    local task_name=""
    local auto_continue=true
    local max_sessions=0
    local session_num=1
    local continue_mode=false
    local resume_last=false
    local enable_network=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --list|-l)
                list_tasks
                exit 0
                ;;
            --task-name|-n)
                task_name="${2:-}"
                shift 2
                ;;
            --continue|-c)
                continue_mode=true
                shift
                ;;
            --no-auto-continue)
                auto_continue=false
                shift
                ;;
            --max-sessions)
                max_sessions="${2:-0}"
                shift 2
                ;;
            --resume-last)
                resume_last=true
                shift
                ;;
            --network)
                enable_network=true
                shift
                ;;
            *)
                task_desc="$1"
                shift
                ;;
        esac
    done

    # Determine task name
    if [ -z "$task_name" ] && [ -n "$task_desc" ]; then
        task_name=$(generate_task_name "$task_desc")
        print_info "Generated task name: $task_name"
    fi

    # Validate
    if [ -z "$task_name" ]; then
        if [ "$continue_mode" = true ]; then
            # Try to find most recent task
            if [ -d "$AUTONOMOUS_DIR" ]; then
                task_name=$(ls -t "$AUTONOMOUS_DIR" 2>/dev/null | head -1) || true
            fi
            if [ -z "$task_name" ]; then
                print_error "No task name provided and no existing tasks found"
                echo "Usage: $0 \"Your task description\""
                echo "       $0 --task-name <name> --continue"
                exit 1
            fi
            print_info "Continuing most recent task: $task_name"
        else
            print_error "No task description or name provided"
            show_help
            exit 1
        fi
    fi

    # Security: Validate task name to prevent path traversal
    if ! validate_task_name "$task_name"; then
        exit 1
    fi

    # Check that codex command is available before starting sessions
    check_dependencies

    local task_dir
    task_dir=$(get_task_dir "$task_name")
    CURRENT_TASK_NAME="$task_name"

    if [ "$enable_network" = true ]; then
        print_warning "Network mode uses --dangerously-bypass-approvals-and-sandbox. Use only in an isolated environment."
    fi

    # Main loop
    while true; do
        echo ""
        print_header "SESSION $session_num - $task_name"

        # Show current progress
        if task_exists "$task_name"; then
            echo "Progress: $(get_progress "$task_dir")"
            echo ""
        fi

        # Determine which agent to run
        if task_exists "$task_name"; then
            # Task list exists - run executor
            run_executor "$task_name" "$resume_last" "$enable_network"
            # Only resume on first iteration if requested
            resume_last=false
        else
            # No task list - run initializer
            if [ -z "$task_desc" ]; then
                print_error "Task '$task_name' not found and no description provided"
                echo "Provide a task description to initialize: $0 \"Your task description\""
                exit 1
            fi
            run_initializer "$task_name" "$task_desc" "$enable_network"
        fi

        # Show progress after session
        echo ""
        echo "=== Progress: $(get_progress "$task_dir") ==="

        # Check completion
        if is_complete "$task_dir"; then
            echo ""
            print_success "ALL TASKS COMPLETED!"
            echo ""
            echo "Task directory: $task_dir"
            echo "Final task list:"
            cat "$task_dir/task_list.md"
            exit 0
        fi

        # Check max sessions
        if [ $max_sessions -gt 0 ] && [ $session_num -ge $max_sessions ]; then
            print_warning "Reached maximum sessions ($max_sessions)"
            exit 0
        fi

        # Auto-continue logic
        if [ "$auto_continue" = true ]; then
            echo ""
            echo "Continuing in $AUTO_CONTINUE_DELAY seconds... (Press Ctrl+C to pause)"

            # Sleep with countdown
            for i in $(seq $AUTO_CONTINUE_DELAY -1 1); do
                echo -ne "\r$i... "
                sleep 1
            done
            echo ""
        else
            echo ""
            print_warning "Auto-continue disabled. Run again to continue."
            exit 0
        fi

        session_num=$((session_num + 1))
    done
}

# Handle Ctrl+C gracefully
trap handle_interrupt INT

# Run main
main "$@"
