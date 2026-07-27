#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
updater="$repo_root/scripts/update-codex-plugins.sh"

temp_root="$(mktemp -d "${TMPDIR:-/tmp}/codex-plugin-update-test.XXXXXX")"
cleanup() {
  find "$temp_root" -depth -delete
}
trap cleanup EXIT

fake_bin="$temp_root/bin"
log_file="$temp_root/codex.log"
mkdir -p "$fake_bin"

cat >"$fake_bin/codex" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  "plugin list --json")
    cat <<'JSON'
{
  "installed": [
    {
      "pluginId": "installed-one@demo",
      "name": "installed-one",
      "marketplaceName": "demo",
      "installed": true,
      "enabled": true
    },
    {
      "pluginId": "disabled-one@demo",
      "name": "disabled-one",
      "marketplaceName": "demo",
      "installed": true,
      "enabled": false
    },
    {
      "pluginId": "local-one@local-market",
      "name": "local-one",
      "marketplaceName": "local-market",
      "installed": true,
      "enabled": true
    }
  ],
  "available": [
    {
      "pluginId": "not-installed@demo",
      "name": "not-installed",
      "marketplaceName": "demo",
      "installed": false,
      "enabled": false
    }
  ]
}
JSON
    ;;
  "plugin marketplace list --json")
    cat <<'JSON'
{
  "marketplaces": [
    {
      "name": "demo",
      "marketplaceSource": {
        "sourceType": "git",
        "source": "https://example.invalid/demo.git"
      }
    },
    {
      "name": "empty-git",
      "marketplaceSource": {
        "sourceType": "git",
        "source": "https://example.invalid/empty.git"
      }
    },
    {
      "name": "local-market",
      "marketplaceSource": {
        "sourceType": "local",
        "source": "/tmp/local-market"
      }
    }
  ]
}
JSON
    ;;
  "plugin marketplace upgrade demo --json")
    printf 'upgrade demo\n' >>"$FAKE_CODEX_LOG"
    printf '{"selectedMarketplaces":["demo"],"upgradedRoots":["/tmp/demo"],"errors":[]}\n'
    ;;
  "plugin marketplace upgrade empty-git --json")
    printf 'upgrade empty-git\n' >>"$FAKE_CODEX_LOG"
    printf '{"selectedMarketplaces":["empty-git"],"upgradedRoots":["/tmp/empty-git"],"errors":[]}\n'
    ;;
  "plugin add installed-one@demo --json")
    printf 'add installed-one@demo\n' >>"$FAKE_CODEX_LOG"
    printf '{"pluginId":"installed-one@demo"}\n'
    ;;
  *)
    printf 'Unexpected codex invocation: %s\n' "$*" >&2
    exit 97
    ;;
esac
EOF
chmod +x "$fake_bin/codex"

PATH="$fake_bin:$PATH" FAKE_CODEX_LOG="$log_file" "$updater" >"$temp_root/output.txt" 2>"$temp_root/error.txt"

expected_log="$temp_root/expected.log"
cat >"$expected_log" <<'EOF'
upgrade demo
upgrade empty-git
add installed-one@demo
EOF

cmp "$expected_log" "$log_file"
grep -F "Skipping disabled installed plugin 'disabled-one@demo'" "$temp_root/error.txt" >/dev/null
grep -F "Skipping marketplace 'local-market': source type is 'local', not 'git'" "$temp_root/error.txt" >/dev/null
if grep -F 'not-installed@demo' "$log_file" >/dev/null; then
  printf 'Updater attempted to install an uninstalled marketplace plugin\n' >&2
  exit 1
fi

: >"$log_file"
PATH="$fake_bin:$PATH" FAKE_CODEX_LOG="$log_file" "$updater" --dry-run --marketplace demo \
  >"$temp_root/dry-run.txt" 2>"$temp_root/dry-run-error.txt"
test ! -s "$log_file"
grep -F 'Would run: codex plugin marketplace upgrade demo --json' "$temp_root/dry-run.txt" >/dev/null
grep -F 'Would run: codex plugin add installed-one@demo --json' "$temp_root/dry-run.txt" >/dev/null

: >"$log_file"
PATH="$fake_bin:$PATH" FAKE_CODEX_LOG="$log_file" "$updater" --marketplace empty-git \
  >"$temp_root/empty.txt" 2>"$temp_root/empty-error.txt"
grep -Fx 'upgrade empty-git' "$log_file" >/dev/null
if grep -F 'add ' "$log_file" >/dev/null; then
  printf 'Updater installed a plugin from an empty marketplace\n' >&2
  exit 1
fi

printf 'Codex Plugin updater test passed.\n'
