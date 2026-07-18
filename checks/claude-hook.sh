#!/usr/bin/env bash
# Claude Code hook adapter for checks/gate.sh (see .claude/settings.json).
#   edit — PostToolUse on Write|Edit: run the gate after markdown edits and
#          block-inject violations back into the agent's context.
#   stop — Stop: refuse to end the turn while the gate is red.
# Exit 0 with no output = nothing to report.
set -uo pipefail

mode=${1:-edit}
input=$(cat)
repo=$(cd "$(dirname "$0")/.." && pwd)

case "$mode" in
  edit)
    f=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')
    case "$f" in *.md) ;; *) exit 0 ;; esac
    ;;
  stop)
    # Guard against block loops: if a Stop hook already blocked once this
    # turn, let the agent stop even if the gate is still red.
    printf '%s' "$input" | jq -e '.stop_hook_active == true' > /dev/null && exit 0
    ;;
esac

out=$("$repo/checks/gate.sh" 2>&1) && exit 0

jq -n --arg out "$out" --arg mode "$mode" '{
  decision: "block",
  reason: ("Convention gate is failing (checks/gate.sh — see the Convention gate section of CLAUDE.md):\n\n" + $out + "\n\nFix the violations, then re-run `make check` to confirm green.")
}'
