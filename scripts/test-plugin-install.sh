#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/test-plugin-install.sh [--keep-temp]

Test the repo marketplace and codex-settings plugin with an isolated CODEX_HOME.
The test stages only tracked and non-ignored working-tree files.

Options:
  --keep-temp  Preserve the temporary directory for debugging.
  -h, --help   Show this help text.
EOF
}

keep_temp=false
while (($#)); do
  case "$1" in
    --keep-temp)
      keep_temp=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
marketplace_manifest="$repo_root/.agents/plugins/marketplace.json"
plugin_manifest="$repo_root/.codex-plugin/plugin.json"

command -v codex >/dev/null || {
  printf 'codex CLI is required\n' >&2
  exit 1
}
command -v python3 >/dev/null || {
  printf 'python3 is required\n' >&2
  exit 1
}
test -f "$marketplace_manifest" || {
  printf 'Missing marketplace manifest: %s\n' "$marketplace_manifest" >&2
  exit 1
}
test -f "$plugin_manifest" || {
  printf 'Missing plugin manifest: %s\n' "$plugin_manifest" >&2
  exit 1
}

mkdir -p "$repo_root/.tmp"
temp_root="$(mktemp -d "$repo_root/.tmp/plugin-install-test.XXXXXX")"
marketplace_root="$temp_root/marketplace"
codex_home="$temp_root/codex-home"

cleanup() {
  if $keep_temp; then
    printf 'Temporary directory preserved: %s\n' "$temp_root"
  else
    find "$temp_root" -depth -delete
  fi
}
trap cleanup EXIT

mkdir -p "$marketplace_root" "$codex_home"
while IFS= read -r -d '' relative_path; do
  source_path="$repo_root/$relative_path"
  destination_path="$marketplace_root/$relative_path"
  if ! test -e "$source_path" && ! test -L "$source_path"; then
    continue
  fi
  mkdir -p "$(dirname "$destination_path")"
  if test -L "$source_path"; then
    cp -P "$source_path" "$destination_path"
  else
    cp -p "$source_path" "$destination_path"
  fi
done < <(
  git -C "$repo_root" ls-files -z --cached --others --exclude-standard
)

test -f "$marketplace_root/.agents/plugins/marketplace.json"
test -f "$marketplace_root/.codex-plugin/plugin.json"

marketplace_add="$(
  CODEX_HOME="$codex_home" codex plugin marketplace add "$marketplace_root" --json
)"
available="$(
  CODEX_HOME="$codex_home" codex plugin list \
    --marketplace codex-settings --available --json
)"
plugin_add="$(
  CODEX_HOME="$codex_home" codex plugin add codex-settings@codex-settings --json
)"
installed="$(
  CODEX_HOME="$codex_home" codex plugin list \
    --marketplace codex-settings --json
)"

MARKETPLACE_ADD="$marketplace_add" \
AVAILABLE="$available" \
PLUGIN_ADD="$plugin_add" \
INSTALLED="$installed" \
python3 - <<'PY'
import json
import os

marketplace_add = json.loads(os.environ["MARKETPLACE_ADD"])
available = json.loads(os.environ["AVAILABLE"])
plugin_add = json.loads(os.environ["PLUGIN_ADD"])
installed = json.loads(os.environ["INSTALLED"])

assert (
    marketplace_add.get("marketplaceName") or marketplace_add.get("name")
) == "codex-settings", marketplace_add
available_items = available.get("available", []) + available.get("installed", [])
assert any(item.get("pluginId") == "codex-settings@codex-settings" for item in available_items), available
assert plugin_add.get("pluginId") == "codex-settings@codex-settings", plugin_add
assert any(
    item.get("pluginId") == "codex-settings@codex-settings"
    and item.get("installed") is True
    for item in installed.get("installed", [])
), installed
PY

version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$plugin_manifest")"
# Version-coupled canary: fail loudly if a future Codex CLI changes its cache layout.
cache_root="$codex_home/plugins/cache/codex-settings/codex-settings/$version"
test -f "$cache_root/.codex-plugin/plugin.json"
test -f "$cache_root/skills/brainstorming/SKILL.md"
test -f "$cache_root/skills/github-fix-issue/SKILL.md"
test -f "$cache_root/skills/github-fix-issue/agents/openai.yaml"
test -f "$cache_root/skills/github-review-pr/SKILL.md"
test -f "$cache_root/skills/github-review-pr/agents/openai.yaml"
test ! -e "$cache_root/prompts"
test ! -e "$cache_root/history.jsonl"
test ! -e "$cache_root/sessions"
test ! -e "$cache_root/memories"
test ! -e "$cache_root/state_5.sqlite"

CODEX_HOME="$codex_home" codex plugin remove codex-settings@codex-settings --json >/dev/null
CODEX_HOME="$codex_home" codex plugin marketplace remove codex-settings --json >/dev/null
test ! -e "$cache_root"

printf 'Codex Plugin install test passed with %s.\n' "$(codex --version)"
