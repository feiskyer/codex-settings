#!/bin/bash
#
# Autonomous Skill - Session Runner
# Executes Codex in non-interactive mode with auto-continuation
#

set -euo pipefail

AUTO_CONTINUE_DELAY=3
CURRENT_TASK_NAME=""
CURRENT_TASK_DIR=""
CURRENT_LOCK_DIR=""
WORKSPACE_ROOT=""
AUTONOMOUS_DIR=""
EXECUTION_CWD=""
CODEX_ARGS=()
LAST_CODEX_EXIT=0
LAST_SESSION_ID=""

if [ -n "${CODEX_PLUGIN_ROOT:-}" ]; then
    SKILL_DIR="${CODEX_PLUGIN_ROOT}/skills/autonomous-skill"
else
    SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

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

release_task_lock() {
    if [ -n "${CURRENT_LOCK_DIR:-}" ] && [ -d "$CURRENT_LOCK_DIR" ]; then
        local owner_pid=""
        if [ -f "$CURRENT_LOCK_DIR/pid" ]; then
            owner_pid="$(cat "$CURRENT_LOCK_DIR/pid" 2>/dev/null || true)"
        fi
        if [ -z "$owner_pid" ] || [ "$owner_pid" = "$$" ]; then
            rm -rf "$CURRENT_LOCK_DIR"
        fi
    fi
}

cleanup() {
    release_task_lock
}

handle_interrupt() {
    echo ""
    release_task_lock
    if [ -n "${CURRENT_TASK_NAME:-}" ]; then
        print_warning "Interrupted. Progress saved in $CURRENT_TASK_DIR/"
        echo "Run again to continue: $0 --task-name $CURRENT_TASK_NAME --continue"
    else
        print_warning "Interrupted."
    fi
    trap - EXIT
    exit 130
}

show_help() {
    echo "Autonomous Skill - Session Runner (Codex)"
    echo ""
    echo "Usage:"
    echo "  bash $0 \"task description\"           Start new task (auto-generates name)"
    echo "  bash $0 --task-name <name> --continue Continue specific task"
    echo "  bash $0 --list                        List all tasks"
    echo "  bash $0 --help                        Show this help"
    echo ""
    echo "Options:"
    echo "  --task-name <name>       Specify task name explicitly (must start with A-Z a-z 0-9; safe chars: . _ -)"
    echo "  --continue, -c           Continue existing task"
    echo "  --no-auto-continue       Don't auto-continue after session"
    echo "  --max-sessions N         Limit to N sessions"
    echo "  --list                   List all existing tasks"
    echo "  --resume-last            Resume the saved Codex session for the selected task"
    echo "  --network                Enable danger-full-access sandbox for tasks that need broader shell access"
    echo ""
    echo "Examples:"
    echo "  bash $0 \"Build a REST API for todo app\""
    echo "  bash $0 --task-name build-rest-api --continue"
    echo "  bash $0 --task-name build-rest-api --continue --resume-last"
    echo "  bash $0 --list"
    echo ""
    echo "Task Directory: <workspace-root>/.autonomous/<task-name> (git root if available, else current directory)"
    echo "Execution Directory: current working directory where the runner was launched"
    echo "Skill Directory: $SKILL_DIR"
    echo "Model Selection: Uses the active Codex config/profile model (no --model override)"
    echo ""
}

detect_workspace_root() {
    if command -v git >/dev/null 2>&1; then
        local git_root=""
        git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
        if [ -n "$git_root" ]; then
            echo "$git_root"
            return
        fi
    fi
    pwd -P
}

resolve_workspace_paths() {
    EXECUTION_CWD="$(pwd -P)"
    WORKSPACE_ROOT="$(detect_workspace_root)"
    AUTONOMOUS_DIR="$WORKSPACE_ROOT/.autonomous"
}

generate_task_name() {
    local desc="${1:-}"
    local result=""

    result="$(printf '%s' "$desc" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | cut -c1-30 | sed 's/^-//' | sed 's/-$//')"

    if [ -z "$result" ]; then
        result="task-$(date +%Y%m%d-%H%M%S)"
        print_warning "Non-alphanumeric description detected, using generated name: $result" >&2
    fi

    printf '%s\n' "$result"
}

validate_task_name() {
    local name="$1"

    if [ -z "$name" ]; then
        print_error "Task name cannot be empty"
        return 1
    fi

    if [[ "$name" == -* ]]; then
        print_error "Task name cannot start with a hyphen"
        return 1
    fi

    if [[ "$name" == .* ]]; then
        print_error "Task name cannot start with a dot"
        return 1
    fi

    if [[ "$name" == *".."* ]] || [[ "$name" == *"/"* ]] || [[ "$name" == *"\\"* ]]; then
        print_error "Invalid task name: '$name' (contains path traversal characters)"
        return 1
    fi

    if [[ ! "$name" =~ ^[A-Za-z0-9._-]+$ ]]; then
        print_error "Invalid task name: '$name' (allowed characters: letters, numbers, dot, underscore, hyphen)"
        return 1
    fi

    return 0
}

require_option_value() {
    local option="$1"
    local value="${2:-}"

    if [ -z "$value" ] || [[ "$value" == --* ]]; then
        print_error "Option '$option' requires a value"
        exit 1
    fi
}

validate_non_negative_integer() {
    local name="$1"
    local value="$2"

    if [[ ! "$value" =~ ^[0-9]+$ ]]; then
        print_error "$name must be a non-negative integer"
        exit 1
    fi
}

check_dependencies() {
    if ! command -v codex >/dev/null 2>&1; then
        print_error "Required command 'codex' not found"
        echo "Please install Codex CLI: https://github.com/openai/codex"
        exit 1
    fi
}

build_codex_args() {
    local enable_network="$1"
    local sandbox_mode="workspace-write"

    if [ "$enable_network" = true ]; then
        sandbox_mode="danger-full-access"
    fi

    CODEX_ARGS=(
        -c 'approval_policy="never"'
        -c "sandbox_mode=\"$sandbox_mode\""
        --skip-git-repo-check
        --json
        -C "$EXECUTION_CWD"
    )
}

ensure_unique_task_name() {
    local base_name="$1"
    local candidate="$base_name"
    local suffix=2

    while [ -e "$AUTONOMOUS_DIR/$candidate" ]; do
        local suffix_part="-$suffix"
        local max_base_len=$((30 - ${#suffix_part}))
        if [ "$max_base_len" -lt 1 ]; then
            max_base_len=1
        fi
        candidate="$(printf '%s' "$base_name" | cut -c1-"$max_base_len")$suffix_part"
        suffix=$((suffix + 1))
    done

    printf '%s\n' "$candidate"
}

get_path_mtime() {
    local path="$1"

    if [ ! -e "$path" ]; then
        echo "0"
        return
    fi

    if stat -f '%m' "$path" >/dev/null 2>&1; then
        stat -f '%m' "$path"
    else
        stat -c '%Y' "$path"
    fi
}

get_task_activity_mtime() {
    local task_dir="$1"
    local latest=0
    local current=0
    local candidate=""

    for candidate in \
        "$task_dir/session.log" \
        "$task_dir/progress.md" \
        "$task_dir/task_list.md" \
        "$task_dir/session.id" \
        "$task_dir"
    do
        current="$(get_path_mtime "$candidate")"
        if [ "$current" -gt "$latest" ]; then
            latest="$current"
        fi
    done

    echo "$latest"
}

find_recent_task_name() {
    local latest_name=""
    local latest_mtime=0
    local task_dir=""
    local task_mtime=0

    if [ ! -d "$AUTONOMOUS_DIR" ]; then
        echo ""
        return
    fi

    for task_dir in "$AUTONOMOUS_DIR"/*; do
        [ -d "$task_dir" ] || continue
        [ -f "$task_dir/task_list.md" ] || continue

        task_mtime="$(get_task_activity_mtime "$task_dir")"
        if [ "$task_mtime" -gt "$latest_mtime" ]; then
            latest_mtime="$task_mtime"
            latest_name="$(basename "$task_dir")"
        fi
    done

    echo "$latest_name"
}

count_total_tasks() {
    local task_list="$1"

    if [ ! -f "$task_list" ]; then
        echo "0"
        return
    fi

    awk '
        /^## Tasks$/ {in_tasks=1; next}
        /^## / && in_tasks {in_tasks=0}
        in_tasks && /^- \[[ x]\] Task [0-9]+:/ {count++}
        END {print count+0}
    ' "$task_list"
}

count_completed_tasks() {
    local task_list="$1"

    if [ ! -f "$task_list" ]; then
        echo "0"
        return
    fi

    awk '
        /^## Tasks$/ {in_tasks=1; next}
        /^## / && in_tasks {in_tasks=0}
        in_tasks && /^- \[x\] Task [0-9]+:/ {count++}
        END {print count+0}
    ' "$task_list"
}

task_list_has_invalid_entries() {
    local task_list="$1"

    awk '
        /^## Tasks$/ {in_tasks=1; next}
        /^## / && in_tasks {in_tasks=0}
        in_tasks && /^- \[/ {
            if ($0 !~ /^- \[[ x]\] Task [0-9]+:/) {
                invalid=1
                next
            }

            line=$0
            sub(/^.*Task /, "", line)
            sub(/:.*/, "", line)
            task_num=line+0

            if (seen && task_num <= previous) {
                invalid=1
                next
            }

            previous=task_num
            seen=1
        }
        END { exit invalid ? 0 : 1 }
    ' "$task_list"
}

list_tasks() {
    print_header "AUTONOMOUS TASKS"

    if [ ! -d "$AUTONOMOUS_DIR" ]; then
        print_warning "No tasks found. Directory $AUTONOMOUS_DIR does not exist."
        echo ""
        return
    fi

    local found=0
    local task_dir=""

    for task_dir in "$AUTONOMOUS_DIR"/*; do
        [ -d "$task_dir" ] || continue

        local task_name=""
        local task_list=""
        local total=0
        local done_count=0
        local percent=0
        local session_info=""

        task_name="$(basename "$task_dir")"
        task_list="$task_dir/task_list.md"

        if [ -f "$task_list" ]; then
            total="$(count_total_tasks "$task_list")"
            done_count="$(count_completed_tasks "$task_list")"

            if [ "$total" -gt 0 ]; then
                percent=$((done_count * 100 / total))
            fi

            if [ -f "$task_dir/session.id" ]; then
                local sid=""
                sid="$(head -c 8 < "$task_dir/session.id")"
                session_info=" [session: ${sid}...]"
            fi

            if [ "$done_count" -eq "$total" ] && [ "$total" -gt 0 ]; then
                echo -e "  ${GREEN}✓${NC} $task_name ($done_count/$total - 100% complete)$session_info"
            else
                echo -e "  ${YELLOW}○${NC} $task_name ($done_count/$total - $percent%)$session_info"
            fi
        else
            echo -e "  ${RED}?${NC} $task_name (no task_list.md)"
        fi

        found=$((found + 1))
    done

    if [ "$found" -eq 0 ]; then
        print_warning "No tasks found in $AUTONOMOUS_DIR/"
    fi

    echo ""
}

task_exists() {
    local task_name="$1"
    [ -f "$AUTONOMOUS_DIR/$task_name/task_list.md" ]
}

task_artifacts_exist() {
    local task_dir="$1"
    [ -e "$task_dir/task_list.md" ] || [ -e "$task_dir/progress.md" ] || [ -e "$task_dir/session.id" ] || [ -e "$task_dir/session.log" ]
}

validate_task_state() {
    local task_dir="$1"
    local context="$2"
    local task_list="$task_dir/task_list.md"
    local progress_file="$task_dir/progress.md"
    local total=0
    local done=0

    if [ ! -f "$task_list" ]; then
        print_error "$context is missing $task_list"
        return 1
    fi

    if [ ! -f "$progress_file" ]; then
        print_error "$context is missing $progress_file"
        return 1
    fi

    total="$(count_total_tasks "$task_list")"
    done="$(count_completed_tasks "$task_list")"

    if [ "$total" -le 0 ]; then
        print_error "$context has an invalid task_list.md (no parseable tasks)"
        return 1
    fi

    if [ "$done" -gt "$total" ]; then
        print_error "$context has an invalid task_list.md (completed tasks exceed total tasks)"
        return 1
    fi

    if task_list_has_invalid_entries "$task_list"; then
        print_error "$context has an invalid task_list.md (contains invalid or out-of-order task entries)"
        return 1
    fi

    return 0
}

get_task_dir() {
    local task_name="$1"
    echo "$AUTONOMOUS_DIR/$task_name"
}

get_progress() {
    local task_dir="$1"
    local task_list="$task_dir/task_list.md"

    echo "$(count_completed_tasks "$task_list")/$(count_total_tasks "$task_list")"
}

is_complete() {
    local task_dir="$1"
    local task_list="$task_dir/task_list.md"
    local total=0
    local done=0

    total="$(count_total_tasks "$task_list")"
    done="$(count_completed_tasks "$task_list")"

    if [ "$total" -gt 0 ] && [ "$done" -eq "$total" ]; then
        return 0
    fi

    return 1
}

extract_session_id() {
    local log_file="$1"
    local id=""

    id="$(grep '"type":"thread.started"' "$log_file" 2>/dev/null | tail -n 1 | sed -n 's/.*"thread_id":"\([^"]*\)".*/\1/p')"
    if [ -z "$id" ]; then
        id="$(grep '"thread_id"' "$log_file" 2>/dev/null | tail -n 1 | sed -n 's/.*"thread_id":"\([^"]*\)".*/\1/p')"
    fi
    if [ -z "$id" ]; then
        id="$(grep '"session_id"' "$log_file" 2>/dev/null | tail -n 1 | sed -n 's/.*"session_id":"\([^"]*\)".*/\1/p')"
    fi

    echo "$id"
}

persist_session_id() {
    local task_dir="$1"
    local session_id="$2"
    local temp_file="$task_dir/session.id.tmp"

    if [ -z "$session_id" ]; then
        return
    fi

    printf '%s\n' "$session_id" > "$temp_file"
    mv "$temp_file" "$task_dir/session.id"
    print_info "Session ID saved: $session_id"
}

render_template() {
    local template_path="$1"
    local task_dir="$2"
    local template=""

    template="$(cat "$template_path")"
    printf '%s' "${template//\{TASK_DIR\}/$task_dir}"
}

run_codex_capture() {
    local task_dir="$1"
    shift

    local run_log=""
    run_log="$(mktemp "$task_dir/session.run.XXXXXX.log")"

    set +e
    "$@" 2>&1 | tee "$run_log"
    LAST_CODEX_EXIT=${PIPESTATUS[0]}
    set -e

    cat "$run_log" >> "$task_dir/session.log"
    LAST_SESSION_ID="$(extract_session_id "$run_log")"
    rm -f "$run_log"
}

acquire_task_lock() {
    local task_dir="$1"
    local lock_dir="$task_dir/.runner.lock"
    local existing_pid=""

    mkdir -p "$task_dir"

    if mkdir "$lock_dir" 2>/dev/null; then
        printf '%s\n' "$$" > "$lock_dir/pid"
        CURRENT_LOCK_DIR="$lock_dir"
        return 0
    fi

    if [ -f "$lock_dir/pid" ]; then
        existing_pid="$(cat "$lock_dir/pid" 2>/dev/null || true)"
    fi

    if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
        print_error "Task '$CURRENT_TASK_NAME' is already running (pid: $existing_pid)"
        return 1
    fi

    print_warning "Removing stale lock for task '$CURRENT_TASK_NAME'${existing_pid:+ (pid: $existing_pid)}"
    rm -rf "$lock_dir"

    if mkdir "$lock_dir" 2>/dev/null; then
        printf '%s\n' "$$" > "$lock_dir/pid"
        CURRENT_LOCK_DIR="$lock_dir"
        return 0
    fi

    print_error "Task '$CURRENT_TASK_NAME' is already running"
    return 1
}

run_initializer() {
    local task_name="$1"
    local task_desc="$2"
    local enable_network="$3"
    local task_dir=""
    local init_prompt=""
    local prompt=""

    task_dir="$(get_task_dir "$task_name")"

    print_header "INITIALIZER SESSION"
    echo "Task: $task_desc"
    echo "Task Name: $task_name"
    echo "Task Directory: $task_dir"
    echo ""

    init_prompt="$(render_template "$SKILL_DIR/templates/initializer-prompt.md" "$task_dir")"
    build_codex_args "$enable_network"

    prompt="Task: $task_desc
Task Name: $task_name
Task Directory: $task_dir

You are the Initializer Agent. Create task_list.md and progress.md in the $task_dir directory. All task files must be created in $task_dir/, not in the current directory.

$init_prompt"

    run_codex_capture "$task_dir" codex exec "${CODEX_ARGS[@]}" "$prompt"
    persist_session_id "$task_dir" "$LAST_SESSION_ID"

    if [ "$LAST_CODEX_EXIT" -ne 0 ]; then
        print_error "Initializer session failed (exit $LAST_CODEX_EXIT)"
        return "$LAST_CODEX_EXIT"
    fi

    if [ ! -f "$task_dir/task_list.md" ] || [ ! -f "$task_dir/progress.md" ]; then
        print_error "Initializer did not create required files in $task_dir"
        return 1
    fi

    if ! validate_task_state "$task_dir" "Initializer output for task '$task_name'"; then
        return 1
    fi

    echo ""
    print_success "Initializer session complete"
}

run_executor() {
    local task_name="$1"
    local resume_last="$2"
    local enable_network="$3"
    local task_dir=""
    local exec_prompt=""
    local prompt=""
    local session_id=""
    local resumed=false

    task_dir="$(get_task_dir "$task_name")"

    print_header "EXECUTOR SESSION"
    echo "Task Name: $task_name"
    echo "Task Directory: $task_dir"
    echo ""

    exec_prompt="$(render_template "$SKILL_DIR/templates/executor-prompt.md" "$task_dir")"
    build_codex_args "$enable_network"

    prompt="Continue working on the task.
Task Name: $task_name
Task Directory: $task_dir
Current Progress: $(get_progress "$task_dir")

You are the Executor Agent. Read $task_dir/task_list.md and $task_dir/progress.md directly before making changes. Do not rely on stale summaries.

$exec_prompt"

    if [ "$resume_last" = true ] && [ -f "$task_dir/session.id" ]; then
        session_id="$(cat "$task_dir/session.id")"
        print_info "Resuming session: $session_id"
        run_codex_capture "$task_dir" codex exec resume "${CODEX_ARGS[@]}" "$session_id" "$prompt"

        if [ "$LAST_CODEX_EXIT" -eq 0 ]; then
            resumed=true
        else
            print_warning "Resume failed for task '$task_name' (exit $LAST_CODEX_EXIT). Falling back to a new session." >&2
        fi
    fi

    if [ "$resumed" = false ]; then
        run_codex_capture "$task_dir" codex exec "${CODEX_ARGS[@]}" "$prompt"
    fi

    persist_session_id "$task_dir" "$LAST_SESSION_ID"

    if [ "$LAST_CODEX_EXIT" -ne 0 ]; then
        print_error "Executor session failed (exit $LAST_CODEX_EXIT)"
        return "$LAST_CODEX_EXIT"
    fi

    if ! validate_task_state "$task_dir" "Executor output for task '$task_name'"; then
        return 1
    fi

    echo ""
    print_success "Executor session complete"
}

main() {
    local task_desc=""
    local task_name=""
    local auto_continue=true
    local max_sessions=0
    local session_num=1
    local continue_mode=false
    local resume_last=false
    local enable_network=false
    local show_help_flag=false
    local list_flag=false
    local task_name_generated=false
    local task_dir=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                show_help_flag=true
                shift
                ;;
            --list|-l)
                list_flag=true
                shift
                ;;
            --task-name|-n)
                require_option_value "$1" "${2:-}"
                task_name="$2"
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
                require_option_value "$1" "${2:-}"
                max_sessions="$2"
                shift 2
                ;;
            --resume-last)
                resume_last=true
                continue_mode=true
                shift
                ;;
            --network)
                enable_network=true
                shift
                ;;
            *)
                if [ -n "$task_desc" ]; then
                    print_error "Unexpected extra argument: $1"
                    exit 1
                fi
                task_desc="$1"
                shift
                ;;
        esac
    done

    validate_non_negative_integer "--max-sessions" "$max_sessions"
    resolve_workspace_paths

    if [ "$show_help_flag" = true ]; then
        show_help
        exit 0
    fi

    if [ "$list_flag" = true ]; then
        list_tasks
        exit 0
    fi

    if [ -z "$task_name" ] && [ -n "$task_desc" ]; then
        task_name="$(generate_task_name "$task_desc")"
        task_name_generated=true
        print_info "Generated task name: $task_name"
    fi

    if [ -z "$task_name" ]; then
        if [ "$continue_mode" = true ]; then
            task_name="$(find_recent_task_name)"
            if [ -z "$task_name" ]; then
                print_error "No task name provided and no existing tasks found"
                echo "Usage: bash $0 \"Your task description\""
                echo "       bash $0 --task-name <name> --continue"
                exit 1
            fi
            print_info "Continuing most recent task: $task_name"
        else
            print_error "No task description or name provided"
            show_help
            exit 1
        fi
    fi

    if ! validate_task_name "$task_name"; then
        exit 1
    fi

    check_dependencies

    mkdir -p "$AUTONOMOUS_DIR"

    if [ "$task_name_generated" = true ] && [ "$continue_mode" = false ]; then
        local unique_task_name=""
        unique_task_name="$(ensure_unique_task_name "$task_name")"
        if [ "$unique_task_name" != "$task_name" ]; then
            print_warning "Task name '$task_name' already exists, using unique name: $unique_task_name"
            task_name="$unique_task_name"
        fi
    fi

    task_dir="$(get_task_dir "$task_name")"
    CURRENT_TASK_NAME="$task_name"
    CURRENT_TASK_DIR="$task_dir"

    if ! acquire_task_lock "$task_dir"; then
        exit 1
    fi

    if [ "$enable_network" = true ]; then
        print_warning "Network mode uses sandbox_mode=danger-full-access with approval_policy=never. Use only in an isolated environment."
    fi

    while true; do
        echo ""
        print_header "SESSION $session_num - $task_name"

        if task_exists "$task_name"; then
            if ! validate_task_state "$task_dir" "Existing task '$task_name'"; then
                exit 1
            fi
            echo "Progress: $(get_progress "$task_dir")"
            echo ""

            if is_complete "$task_dir"; then
                echo ""
                print_success "ALL TASKS COMPLETED!"
                echo ""
                echo "Task directory: $task_dir"
                echo "Final task list:"
                cat "$task_dir/task_list.md"
                exit 0
            fi
        fi

        if task_exists "$task_name"; then
            run_executor "$task_name" "$resume_last" "$enable_network"
        else
            if task_artifacts_exist "$task_dir"; then
                print_error "Task '$task_name' is in an invalid state. Ensure task_list.md and progress.md both exist and task_list.md still contains valid Task N entries."
                exit 1
            fi
            if [ -z "$task_desc" ]; then
                print_error "Task '$task_name' not found and no description provided"
                echo "Provide a task description to initialize: bash $0 \"Your task description\""
                exit 1
            fi
            run_initializer "$task_name" "$task_desc" "$enable_network"
        fi

        if ! validate_task_state "$task_dir" "Task '$task_name' state after session $session_num"; then
            exit 1
        fi

        echo ""
        echo "=== Progress: $(get_progress "$task_dir") ==="

        if is_complete "$task_dir"; then
            echo ""
            print_success "ALL TASKS COMPLETED!"
            echo ""
            echo "Task directory: $task_dir"
            echo "Final task list:"
            cat "$task_dir/task_list.md"
            exit 0
        fi

        if [ "$max_sessions" -gt 0 ] && [ "$session_num" -ge "$max_sessions" ]; then
            print_warning "Reached maximum sessions ($max_sessions)"
            exit 0
        fi

        if [ "$auto_continue" = true ]; then
            echo ""
            echo "Continuing in $AUTO_CONTINUE_DELAY seconds... (Press Ctrl+C to pause)"
            local i=0
            for i in $(seq "$AUTO_CONTINUE_DELAY" -1 1); do
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

trap cleanup EXIT
trap handle_interrupt INT TERM

main "$@"
