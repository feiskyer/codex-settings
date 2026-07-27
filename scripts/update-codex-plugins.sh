#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/update-codex-plugins.sh [options]

Refresh configured Git marketplaces and reinstall only the enabled plugins that
were already installed before the refresh. Uninstalled marketplace entries are
never selected.

Options:
  -m, --marketplace NAME  Limit updates to a configured marketplace. Repeatable.
      --dry-run           Print the planned Codex commands without changing state.
  -h, --help              Show this help text.

Environment:
  CODEX_HOME              Use a non-default Codex home when set.

Disabled installed plugins are skipped because `codex plugin add` enables the
target plugin. Local and managed marketplaces are skipped because
`codex plugin marketplace upgrade` refreshes Git marketplaces only.
EOF
}

dry_run=false
marketplace_filters=()
marketplace_filter_count=0

while (($#)); do
  case "$1" in
    -m|--marketplace)
      if (($# < 2)) || [[ -z "$2" ]]; then
        printf 'Missing marketplace name after %s\n' "$1" >&2
        exit 2
      fi
      marketplace_filters+=("$2")
      marketplace_filter_count=$((marketplace_filter_count + 1))
      shift
      ;;
    --dry-run)
      dry_run=true
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

command -v codex >/dev/null || {
  printf 'codex CLI is required\n' >&2
  exit 1
}
command -v python3 >/dev/null || {
  printf 'python3 is required\n' >&2
  exit 1
}

temp_root="$(mktemp -d "${TMPDIR:-/tmp}/codex-plugin-update.XXXXXX")"
cleanup() {
  find "$temp_root" -depth -delete
}
trap cleanup EXIT

installed_json="$temp_root/installed.json"
marketplaces_json="$temp_root/marketplaces.json"
filters_file="$temp_root/marketplace-filters.txt"
marketplace_targets="$temp_root/marketplaces.tsv"
targets_tsv="$temp_root/targets.tsv"

: >"$filters_file"
if ((marketplace_filter_count > 0)); then
  printf '%s\n' "${marketplace_filters[@]}" >"$filters_file"
fi

# Freeze the installed set before refreshing any marketplace. Do not use
# `--available`: available marketplace entries must never become update targets.
codex plugin list --json >"$installed_json"
codex plugin marketplace list --json >"$marketplaces_json"

python3 - "$installed_json" "$marketplaces_json" "$filters_file" \
  "$marketplace_targets" "$targets_tsv" <<'PY'
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

installed_path = Path(sys.argv[1])
marketplaces_path = Path(sys.argv[2])
filters_path = Path(sys.argv[3])
marketplace_targets_path = Path(sys.argv[4])
targets_path = Path(sys.argv[5])
requested = [line for line in filters_path.read_text().splitlines() if line]
explicit_filter = bool(requested)

segment = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Failed to read {label} JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Invalid {label} JSON: expected an object")
    return value


installed_payload = load_json(installed_path, "installed plugin list")
marketplaces_payload = load_json(marketplaces_path, "marketplace list")

installed_items = installed_payload.get("installed")
marketplace_items = marketplaces_payload.get("marketplaces")
if not isinstance(installed_items, list):
    raise SystemExit("Invalid plugin list JSON: missing installed array")
if not isinstance(marketplace_items, list):
    raise SystemExit("Invalid marketplace list JSON: missing marketplaces array")

configured = {}
for item in marketplace_items:
    if not isinstance(item, dict):
        continue
    name = item.get("name")
    if not isinstance(name, str) or not segment.fullmatch(name):
        continue
    source = item.get("marketplaceSource")
    source_type = source.get("sourceType") if isinstance(source, dict) else None
    configured[name] = source_type or "unknown"

enabled_by_marketplace = defaultdict(list)
disabled_by_marketplace = defaultdict(list)
for item in installed_items:
    if not isinstance(item, dict) or item.get("installed") is not True:
        continue
    plugin_id = item.get("pluginId")
    marketplace = item.get("marketplaceName")
    if not isinstance(plugin_id, str) or not isinstance(marketplace, str):
        raise SystemExit("Invalid installed plugin entry: missing pluginId or marketplaceName")
    if not segment.fullmatch(marketplace):
        raise SystemExit(f"Invalid marketplace name in installed plugin entry: {marketplace!r}")
    if "@" not in plugin_id or plugin_id.rsplit("@", 1)[1] != marketplace:
        raise SystemExit(f"Invalid installed plugin ID: {plugin_id!r}")
    plugin_name = plugin_id.rsplit("@", 1)[0]
    if not segment.fullmatch(plugin_name):
        raise SystemExit(f"Invalid plugin name in installed plugin ID: {plugin_id!r}")
    if item.get("enabled") is True:
        enabled_by_marketplace[marketplace].append(plugin_id)
    else:
        disabled_by_marketplace[marketplace].append(plugin_id)

if requested:
    seen = set()
    selected = []
    for name in requested:
        if not segment.fullmatch(name):
            raise SystemExit(f"Invalid marketplace name: {name!r}")
        if name not in seen:
            seen.add(name)
            selected.append(name)
else:
    selected = sorted(configured)

marketplace_targets = []
targets = []
for marketplace in selected:
    if marketplace not in configured:
        message = f"Marketplace {marketplace!r} is not configured"
        if explicit_filter:
            raise SystemExit(message)
        print(f"Skipping: {message}", file=sys.stderr)
        continue

    source_type = configured[marketplace]
    if source_type != "git":
        print(
            f"Skipping marketplace {marketplace!r}: source type is {source_type!r}, not 'git'",
            file=sys.stderr,
        )
        continue

    marketplace_targets.append(marketplace)

    for plugin_id in sorted(set(disabled_by_marketplace[marketplace])):
        print(
            f"Skipping disabled installed plugin {plugin_id!r} to preserve its disabled state",
            file=sys.stderr,
        )

    enabled = sorted(set(enabled_by_marketplace[marketplace]))
    targets.extend((marketplace, plugin_id) for plugin_id in enabled)

marketplace_targets_path.write_text("".join(f"{marketplace}\n" for marketplace in marketplace_targets))
targets_path.write_text("".join(f"{marketplace}\t{plugin_id}\n" for marketplace, plugin_id in targets))
PY

if [[ ! -s "$marketplace_targets" ]]; then
  printf 'No configured Git marketplaces to update.\n'
  exit 0
fi

marketplace_count=0
plugin_count=0

while IFS= read -r marketplace; do
  marketplace_count=$((marketplace_count + 1))
  if $dry_run; then
    printf 'Would run: codex plugin marketplace upgrade %q --json\n' "$marketplace"
  else
    printf 'Refreshing marketplace %s...\n' "$marketplace"
    codex plugin marketplace upgrade "$marketplace" --json
  fi
done <"$marketplace_targets"

while IFS=$'\t' read -r marketplace plugin_id; do
  plugin_count=$((plugin_count + 1))
  if $dry_run; then
    printf 'Would run: codex plugin add %q --json\n' "$plugin_id"
  else
    printf 'Updating installed plugin %s...\n' "$plugin_id"
    codex plugin add "$plugin_id" --json
  fi
done <"$targets_tsv"

if $dry_run; then
  printf 'Dry run complete: %d marketplace(s), %d installed plugin(s).\n' \
    "$marketplace_count" "$plugin_count"
else
  printf 'Update complete: %d marketplace(s), %d installed plugin(s).\n' \
    "$marketplace_count" "$plugin_count"
  printf 'Start a new Codex session to load the updated plugins.\n'
fi
