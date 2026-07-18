#!/usr/bin/env bash
# Convention gate — mechanical checks for the repo rules in CLAUDE.md.
# Dependency-free: bash + git + grep/sed/awk. To add a rule: write a
# rule_* function that calls `fail`, then append it to RULES at the bottom.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)"

FAILURES=0

# fail <file> <rule> <message>
fail() {
  printf '%s: %s: %s\n' "$1" "$2" "$3" >&2
  FAILURES=$((FAILURES + 1))
}

# Tracked plus untracked-but-not-ignored, so new docs are checked before `git add`.
tracked_md() { git ls-files --cached --others --exclude-standard '*.md'; }

# Every doc links back to the canon entrypoint.
rule_doc_backlink() {
  local f
  for f in $(tracked_md); do
    case "$f" in
      CLAUDE.md | AGENTS.md | AGENT.md) continue ;;
    esac
    if ! grep -Eq '\]\([^)]*(CLAUDE|AGENTS)\.md' "$f"; then
      fail "$f" doc-backlink "no markdown link back to CLAUDE.md / AGENTS.md"
    fi
  done
}

# The agent-guidance entrypoints stay symlinks to CLAUDE.md.
rule_symlink_integrity() {
  local l
  for l in AGENTS.md AGENT.md; do
    if [ ! -L "$l" ]; then
      fail "$l" symlink-integrity "must be a symlink to CLAUDE.md"
    elif [ "$(readlink "$l")" != "CLAUDE.md" ]; then
      fail "$l" symlink-integrity "points at '$(readlink "$l")', expected CLAUDE.md"
    fi
  done
}

# Relative markdown link targets must exist on disk. Fenced code blocks are
# skipped — links inside ``` fences are content being quoted, not document links.
strip_fences() { awk '/^[[:space:]]*```/ { infence = !infence; next } !infence'; }

rule_links_resolve() {
  local f dir target resolved
  for f in $(tracked_md); do
    dir=$(dirname "$f")
    while IFS= read -r target; do
      case "$target" in
        '' | 'http://'* | 'https://'* | 'mailto:'* | '#'*) continue ;;
      esac
      target=${target%%#*}
      [ -z "$target" ] && continue
      case "$target" in
        /*) resolved=".$target" ;;
        *) resolved="$dir/$target" ;;
      esac
      if [ ! -e "$resolved" ]; then
        fail "$f" links-resolve "broken link: $target"
      fi
    done < <(strip_fences < "$f" | grep -oE '\]\([^)]+\)' | sed -E 's/^\]\(//; s/\)$//' | awk '{print $1}')
  done
}

RULES='rule_doc_backlink rule_symlink_integrity rule_links_resolve'
for rule in $RULES; do "$rule"; done

if [ "$FAILURES" -gt 0 ]; then
  echo "conventions: $FAILURES violation(s)" >&2
  exit 1
fi
echo "conventions: all checks passed"
