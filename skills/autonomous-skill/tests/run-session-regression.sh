#!/bin/bash

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="$SKILL_DIR/scripts/run-session.sh"

TEST_ROOT="$(mktemp -d /tmp/autonomous-skill-test-XXXXXX)"
trap 'rm -rf "$TEST_ROOT"' EXIT

PASS_COUNT=0
FAIL_COUNT=0

fail() {
    echo "FAIL: $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

pass() {
    echo "PASS: $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    local message="$3"

    if [[ "$haystack" == *"$needle"* ]]; then
        pass "$message"
    else
        fail "$message"
        echo "  expected to contain: $needle"
        echo "  actual: $haystack"
    fi
}

assert_not_contains() {
    local haystack="$1"
    local needle="$2"
    local message="$3"

    if [[ "$haystack" == *"$needle"* ]]; then
        fail "$message"
        echo "  unexpected content: $needle"
        echo "  actual: $haystack"
    else
        pass "$message"
    fi
}

assert_file_exists() {
    local path="$1"
    local message="$2"

    if [ -e "$path" ]; then
        pass "$message"
    else
        fail "$message"
        echo "  missing: $path"
    fi
}

assert_file_missing() {
    local path="$1"
    local message="$2"

    if [ -e "$path" ]; then
        fail "$message"
        echo "  unexpected file: $path"
    else
        pass "$message"
    fi
}

assert_exit_code() {
    local actual="$1"
    local expected="$2"
    local message="$3"

    if [ "$actual" -eq "$expected" ]; then
        pass "$message"
    else
        fail "$message"
        echo "  expected exit: $expected"
        echo "  actual exit: $actual"
    fi
}

make_fake_codex() {
    local bin_dir="$1"
    local mode="$2"
    mkdir -p "$bin_dir"

    cat > "$bin_dir/codex" <<EOF
#!/bin/bash
set -euo pipefail
printf '%s\n' "\$*" >> "\${FAKE_CODEX_INVOCATIONS}"

case "$mode" in
  success)
    printf '{"type":"thread.started","thread_id":"fake-thread-1"}\n'
    ;;
  success-with-files)
    printf '{"type":"thread.started","thread_id":"fake-thread-1"}\n'
    if [[ "\$*" == *"Initializer Agent"* ]]; then
      task_dir="\${FAKE_TASK_DIR:-}"
      if [ -z "\$task_dir" ]; then
        task_dir=\$(printf '%s' "\$*" | sed -n 's/.*Task Directory: \([^[:space:]]*\).*/\1/p')
      fi
      mkdir -p "\$task_dir"
      cat > "\$task_dir/task_list.md" <<'TASK'
# Task List: Demo
## Tasks
- [ ] Task 1: demo
TASK
      cat > "\$task_dir/progress.md" <<'PROGRESS'
# Progress Log
PROGRESS
    fi
    ;;
  resume-fails-then-exec-succeeds)
    if [ "\${1:-}" = "exec" ] && [ "\${2:-}" = "resume" ]; then
      printf '{"type":"thread.started","thread_id":"resume-thread"}\n'
      exit 23
    fi
    printf '{"type":"thread.started","thread_id":"fresh-thread"}\n'
    ;;
  log-args)
    printf '{"type":"thread.started","thread_id":"log-thread"}\n'
    ;;
  break-task-state)
    printf '{"type":"thread.started","thread_id":"break-thread"}\n'
    if [[ "\$*" == *"Executor Agent"* ]]; then
      task_dir="\${FAKE_TASK_DIR:-}"
      if [ -z "\$task_dir" ]; then
        task_dir=\$(printf '%s' "\$*" | sed -n 's/.*Task Directory: \([^[:space:]]*\).*/\1/p')
      fi
      cat > "\$task_dir/task_list.md" <<'TASK'
# Task List
## Tasks
- [ ] 1. invalid
TASK
    fi
    ;;
  *)
    echo "unknown fake codex mode: $mode" >&2
    exit 99
    ;;
esac
EOF

    chmod +x "$bin_dir/codex"
}

run_case() {
    local case_name="$1"
    shift

    local case_dir="$TEST_ROOT/$case_name"
    mkdir -p "$case_dir/bin" "$case_dir/work"
    export FAKE_CODEX_INVOCATIONS="$case_dir/invocations.log"
    : > "$FAKE_CODEX_INVOCATIONS"

    (
        export PATH="$case_dir/bin:$PATH"
        cd "$case_dir/work"
        set +e
        bash "$SCRIPT_PATH" "$@" >"$case_dir/stdout.log" 2>"$case_dir/stderr.log"
        echo $? >"$case_dir/exit_code"
    )
}

test_non_ascii_task_name() {
    local case_name="non-ascii-task-name"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "success-with-files"
    unset FAKE_TASK_DIR

    run_case "$case_name" "中文任务" --no-auto-continue --max-sessions 1

    local stderr_text
    stderr_text="$(cat "$TEST_ROOT/$case_name/stderr.log")"
    assert_contains "$stderr_text" "Non-alphanumeric description detected" "非 ASCII 任务名会给出 warning"

    local generated_dir
    generated_dir="$(find "$TEST_ROOT/$case_name/work/.autonomous" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
    assert_contains "$generated_dir" "/task-" "非 ASCII 任务名会回退到 task- 时间戳目录"
    assert_not_contains "$generated_dir" $'\033' "不会生成带 ANSI 的异常目录"
}

test_initializer_requires_files() {
    local case_name="initializer-requires-files"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "success"
    export FAKE_TASK_DIR="$TEST_ROOT/$case_name/work/.autonomous/build-api"

    run_case "$case_name" "Build API" --no-auto-continue --max-sessions 1

    local exit_code
    exit_code="$(cat "$TEST_ROOT/$case_name/exit_code")"
    local combined_text
    combined_text="$(cat "$TEST_ROOT/$case_name/stdout.log" "$TEST_ROOT/$case_name/stderr.log")"
    assert_exit_code "$exit_code" 1 "initializer 缺少任务文件时应失败"
    assert_contains "$combined_text" "Initializer did not create required files" "initializer 缺少文件时会给出明确错误"
}

test_resume_fallback() {
    local case_name="resume-fallback"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "resume-fails-then-exec-succeeds"
    mkdir -p "$TEST_ROOT/$case_name/work/.autonomous/existing"
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/task_list.md" <<'EOF_TASK'
# Task List
## Tasks
- [ ] Task 1: demo
EOF_TASK
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/progress.md" <<'EOF_PROGRESS'
# Progress Log
EOF_PROGRESS
    echo "stale-session" > "$TEST_ROOT/$case_name/work/.autonomous/existing/session.id"

    run_case "$case_name" --task-name existing --continue --resume-last --no-auto-continue --max-sessions 1

    local exit_code
    exit_code="$(cat "$TEST_ROOT/$case_name/exit_code")"
    local combined_text
    combined_text="$(cat "$TEST_ROOT/$case_name/stdout.log" "$TEST_ROOT/$case_name/stderr.log")"
    local invocations
    invocations="$(cat "$TEST_ROOT/$case_name/invocations.log")"
    local invocation_count
    invocation_count="$(grep -c '^exec' "$TEST_ROOT/$case_name/invocations.log" || true)"

    assert_exit_code "$exit_code" 0 "resume 失败后会自动回退到新 session"
    assert_contains "$combined_text" "Resume failed" "resume 失败会输出告警"
    assert_contains "$invocations" "exec resume" "会先尝试 resume"
    assert_exit_code "$invocation_count" 2 "resume 失败后会追加一次普通 exec"
}

test_recent_task_ignores_plain_files() {
    local case_name="recent-task-selection"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "success-with-files"
    mkdir -p "$TEST_ROOT/$case_name/work/.autonomous/good"
    cat > "$TEST_ROOT/$case_name/work/.autonomous/good/task_list.md" <<'EOF_TASK'
# Task List
## Tasks
- [ ] Task 1: demo
EOF_TASK
    cat > "$TEST_ROOT/$case_name/work/.autonomous/good/progress.md" <<'EOF_PROGRESS'
# Progress Log
EOF_PROGRESS
    touch "$TEST_ROOT/$case_name/work/.autonomous/zzz-file"
    export FAKE_TASK_DIR="$TEST_ROOT/$case_name/work/.autonomous/good"

    run_case "$case_name" --continue --no-auto-continue --max-sessions 1

    local stdout_text
    stdout_text="$(cat "$TEST_ROOT/$case_name/stdout.log")"
    assert_contains "$stdout_text" "Continuing most recent task: good" "继续最近任务时只选择有效目录"
}

test_executor_prompt_omits_full_state() {
    local case_name="prompt-omits-full-state"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "log-args"
    mkdir -p "$TEST_ROOT/$case_name/work/.autonomous/existing"
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/task_list.md" <<'EOF_TASK'
# Task List
## Tasks
- [ ] Task 1: sentinel-task-list
EOF_TASK
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/progress.md" <<'EOF_PROGRESS'
# Progress Log
sentinel-progress-notes
EOF_PROGRESS

    run_case "$case_name" --task-name existing --continue --no-auto-continue --max-sessions 1

    local invocations
    invocations="$(cat "$TEST_ROOT/$case_name/invocations.log")"
    assert_not_contains "$invocations" "sentinel-task-list" "executor prompt 不再内联完整 task_list"
    assert_not_contains "$invocations" "sentinel-progress-notes" "executor prompt 不再内联完整 progress"
}

test_git_root_autonomous_dir() {
    local case_name="git-root-autonomous-dir"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "success-with-files"
    mkdir -p "$TEST_ROOT/$case_name/work/repo/subdir"
    (
        cd "$TEST_ROOT/$case_name/work/repo"
        git init >/dev/null 2>&1
    )
    export FAKE_TASK_DIR="$TEST_ROOT/$case_name/work/repo/.autonomous/build-api"

    (
        export PATH="$TEST_ROOT/$case_name/bin:$PATH"
        cd "$TEST_ROOT/$case_name/work/repo/subdir"
        set +e
        bash "$SCRIPT_PATH" "Build API" --no-auto-continue --max-sessions 1 >"$TEST_ROOT/$case_name/stdout.log" 2>"$TEST_ROOT/$case_name/stderr.log"
        echo $? >"$TEST_ROOT/$case_name/exit_code"
    )

    assert_file_exists "$TEST_ROOT/$case_name/work/repo/.autonomous/build-api" "git 仓库内会把 .autonomous 写到 repo root"
    assert_file_missing "$TEST_ROOT/$case_name/work/repo/subdir/.autonomous/build-api" "git 子目录下不会误写本地 .autonomous"
}

test_progress_output_is_clean() {
    local case_name="progress-output-clean"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "log-args"
    mkdir -p "$TEST_ROOT/$case_name/work/.autonomous/existing"
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/task_list.md" <<'EOF_TASK'
# Task List
## Tasks
- [ ] Task 1: demo
EOF_TASK
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/progress.md" <<'EOF_PROGRESS'
# Progress Log
EOF_PROGRESS

    run_case "$case_name" --task-name existing --continue --no-auto-continue --max-sessions 1

    local stdout_text
    stdout_text="$(cat "$TEST_ROOT/$case_name/stdout.log")"
    assert_contains "$stdout_text" "Progress: 0/1" "0 命中任务时进度输出保持 0/1"
}

test_invalid_task_name_rejected() {
    local case_name="invalid-task-name"

    run_case "$case_name" --task-name . --no-auto-continue --max-sessions 1

    local exit_code
    exit_code="$(cat "$TEST_ROOT/$case_name/exit_code")"
    local combined_text
    combined_text="$(cat "$TEST_ROOT/$case_name/stdout.log" "$TEST_ROOT/$case_name/stderr.log")"
    assert_exit_code "$exit_code" 1 "任务名 dot 会被拒绝"
    assert_contains "$combined_text" "Task name cannot start with a dot" "非法任务名会输出明确错误"

    run_case "${case_name}-hidden" --task-name .hidden --no-auto-continue --max-sessions 1

    exit_code="$(cat "$TEST_ROOT/${case_name}-hidden/exit_code")"
    combined_text="$(cat "$TEST_ROOT/${case_name}-hidden/stdout.log" "$TEST_ROOT/${case_name}-hidden/stderr.log")"
    assert_exit_code "$exit_code" 1 "点前缀任务名会被拒绝"
    assert_contains "$combined_text" "Task name cannot start with a dot" "点前缀任务名也会输出明确错误"
}

test_stale_lock_is_recovered() {
    local case_name="stale-lock-recovery"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "success-with-files"
    mkdir -p "$TEST_ROOT/$case_name/work/.autonomous/demo/.runner.lock"
    printf '999999\n' > "$TEST_ROOT/$case_name/work/.autonomous/demo/.runner.lock/pid"
    export FAKE_TASK_DIR="$TEST_ROOT/$case_name/work/.autonomous/demo"

    run_case "$case_name" --task-name demo "Demo task" --no-auto-continue --max-sessions 1

    local exit_code
    exit_code="$(cat "$TEST_ROOT/$case_name/exit_code")"
    local combined_text
    combined_text="$(cat "$TEST_ROOT/$case_name/stdout.log" "$TEST_ROOT/$case_name/stderr.log")"
    assert_exit_code "$exit_code" 0 "stale lock 会被自动清理并继续执行"
    assert_contains "$combined_text" "stale lock" "清理 stale lock 时会输出提示"
    assert_file_exists "$TEST_ROOT/$case_name/work/.autonomous/demo/task_list.md" "恢复 stale lock 后会继续初始化任务"
}

test_generated_task_name_collision_creates_new_task() {
    local case_name="generated-task-name-collision"
    local existing_name="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    local unique_name="aaaaaaaaaaaaaaaaaaaaaaaaaaaa-2"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "success-with-files"
    mkdir -p "$TEST_ROOT/$case_name/work/.autonomous/$existing_name"
    cat > "$TEST_ROOT/$case_name/work/.autonomous/$existing_name/task_list.md" <<'EOF_TASK'
# Task List
## Tasks
- [ ] Task 1: existing
EOF_TASK
    cat > "$TEST_ROOT/$case_name/work/.autonomous/$existing_name/progress.md" <<'EOF_PROGRESS'
# Progress Log
EOF_PROGRESS
    export FAKE_TASK_DIR="$TEST_ROOT/$case_name/work/.autonomous/$unique_name"

    run_case "$case_name" "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" --no-auto-continue --max-sessions 1

    local exit_code
    exit_code="$(cat "$TEST_ROOT/$case_name/exit_code")"
    local stdout_text
    stdout_text="$(cat "$TEST_ROOT/$case_name/stdout.log")"
    local dir_count
    dir_count="$(find "$TEST_ROOT/$case_name/work/.autonomous" -mindepth 2 -maxdepth 2 -name task_list.md | wc -l | tr -d ' ')"
    assert_exit_code "$exit_code" 0 "任务名碰撞后新任务初始化仍然成功"
    assert_contains "$stdout_text" "INITIALIZER SESSION" "任务名碰撞时会创建新任务而不是误续跑旧任务"
    assert_exit_code "$dir_count" 2 "任务名碰撞后会保留两个独立任务目录"
}

test_incomplete_task_state_fails_fast() {
    local case_name="incomplete-task-state"
    mkdir -p "$TEST_ROOT/$case_name/work/.autonomous/existing"
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/task_list.md" <<'EOF_TASK'
# Task List
## Tasks
- [ ] Task 1: demo
EOF_TASK

    run_case "$case_name" --task-name existing --continue --no-auto-continue --max-sessions 1

    local exit_code
    exit_code="$(cat "$TEST_ROOT/$case_name/exit_code")"
    local combined_text
    combined_text="$(cat "$TEST_ROOT/$case_name/stdout.log" "$TEST_ROOT/$case_name/stderr.log")"
    assert_exit_code "$exit_code" 1 "缺失 progress.md 时会 fail fast"
    assert_contains "$combined_text" "is missing" "缺失状态文件时会输出明确错误"
}

test_executor_invalid_state_after_run_fails() {
    local case_name="executor-invalid-state-after-run"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "break-task-state"
    mkdir -p "$TEST_ROOT/$case_name/work/.autonomous/existing"
    export FAKE_TASK_DIR="$TEST_ROOT/$case_name/work/.autonomous/existing"
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/task_list.md" <<'EOF_TASK'
# Task List
## Tasks
- [ ] Task 1: demo
EOF_TASK
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/progress.md" <<'EOF_PROGRESS'
# Progress Log
EOF_PROGRESS

    run_case "$case_name" --task-name existing --continue --no-auto-continue --max-sessions 1

    local exit_code
    exit_code="$(cat "$TEST_ROOT/$case_name/exit_code")"
    local combined_text
    combined_text="$(cat "$TEST_ROOT/$case_name/stdout.log" "$TEST_ROOT/$case_name/stderr.log")"
    assert_exit_code "$exit_code" 1 "executor 破坏状态文件后会 fail fast"
    assert_contains "$combined_text" "invalid task_list.md" "状态损坏时会输出明确错误"
}

test_mixed_valid_and_invalid_task_entries_fail() {
    local case_name="mixed-valid-invalid-task-entries"
    make_fake_codex "$TEST_ROOT/$case_name/bin" "log-args"
    mkdir -p "$TEST_ROOT/$case_name/work/.autonomous/existing"
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/task_list.md" <<'EOF_TASK'
# Task List
## Tasks
- [ ] Task 1: valid
- [ ] 2. invalid
EOF_TASK
    cat > "$TEST_ROOT/$case_name/work/.autonomous/existing/progress.md" <<'EOF_PROGRESS'
# Progress Log
EOF_PROGRESS

    run_case "$case_name" --task-name existing --continue --no-auto-continue --max-sessions 1

    local exit_code
    exit_code="$(cat "$TEST_ROOT/$case_name/exit_code")"
    local combined_text
    combined_text="$(cat "$TEST_ROOT/$case_name/stdout.log" "$TEST_ROOT/$case_name/stderr.log")"
    assert_exit_code "$exit_code" 1 "混合合法和非法任务行时会 fail fast"
    assert_contains "$combined_text" "invalid task_list.md" "混合非法任务行时会输出明确错误"
}

test_non_ascii_task_name
test_initializer_requires_files
test_resume_fallback
test_recent_task_ignores_plain_files
test_executor_prompt_omits_full_state
test_git_root_autonomous_dir
test_progress_output_is_clean
test_invalid_task_name_rejected
test_stale_lock_is_recovered
test_generated_task_name_collision_creates_new_task
test_incomplete_task_state_fails_fast
test_executor_invalid_state_after_run_fails
test_mixed_valid_and_invalid_task_entries_fail

echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -ne 0 ]; then
    exit 1
fi
