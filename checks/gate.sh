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

# Tracked plus untracked-but-not-ignored, so new files are checked before `git add`.
tracked_files() { git ls-files --cached --others --exclude-standard "$1"; }
tracked_md() { tracked_files '*.md'; }

# Collapse '.' and '..' segments without touching the filesystem (no realpath
# on stock macOS). Links escaping the repo root come out mangled and simply
# won't match a tracked file — links-resolve reports those separately.
norm_path() {
  local out= part
  local IFS=/
  for part in $1; do
    case "$part" in
      '' | '.') ;;
      '..') case "$out" in */*) out=${out%/*} ;; *) out= ;; esac ;;
      *) if [ -n "$out" ]; then out=$out/$part; else out=$part; fi ;;
    esac
  done
  printf '%s\n' "$out"
}

# Print the repo-relative .md files a doc links to (fenced code ignored).
md_links_of() {
  local f=$1 dir target
  dir=$(dirname "$f")
  strip_fences < "$f" | grep -oE '\]\([^)]+\)' | sed -E 's/^\]\(//; s/\)$//' \
    | awk '{print $1}' | while IFS= read -r target; do
      case "$target" in '' | 'http://'* | 'https://'* | 'mailto:'* | '#'*) continue ;; esac
      target=${target%%#*}
      [ -z "$target" ] && continue
      case "$target" in
        /*) target=$(norm_path ".$target") ;;
        *) target=$(norm_path "$dir/$target") ;;
      esac
      case "$target" in *.md) printf '%s\n' "$target" ;; esac
    done
}

# Every doc is reachable FROM CLAUDE.md by following markdown links forward
# (multi-hop is fine). CLAUDE.md is the map; nothing may be off it.
rule_doc_reachable() {
  local queue="CLAUDE.md" visited=" CLAUDE.md " f l
  while [ -n "$queue" ]; do
    set -- $queue
    f=$1
    shift
    queue="$*"
    [ -e "$f" ] || continue
    for l in $(md_links_of "$f"); do
      case "$visited" in
        *" $l "*) ;;
        *) visited="$visited$l " queue="$queue $l" ;;
      esac
    done
  done
  for f in $(tracked_md); do
    case "$f" in AGENTS.md | AGENT.md) continue ;; esac
    case "$visited" in
      *" $f "*) ;;
      *) fail "$f" doc-reachable "not reachable from CLAUDE.md via markdown links (multi-hop ok)" ;;
    esac
  done
}

# The service contract requires a real healthcheck: a probe that can never
# fail is not a probe. Catches the template placeholder in any YAML spelling —
# flow or block list, quoted or not, CMD or CMD-SHELL, true or /bin/true.
# (The transient smoke-test copy is gitignored, so tracked_files skips it.)
has_placeholder_probe() {
  tr ',' ' ' < "$1" | tr -d "[]\"'" | awk '
    function judge() {
      gsub(/[[:space:]]+/, " ", items); sub(/^ /, "", items); sub(/ $/, "", items)
      if (items == "CMD true" || items == "CMD /bin/true" || \
          items == "CMD-SHELL true" || items == "CMD-SHELL /bin/true" || \
          items == "true" || items == "/bin/true") found = 1
      items = ""; intest = 0
    }
    /test:/ { t = $0; sub(/.*test:/, "", t); intest = 1; items = t; next }
    intest && $1 == "-" { sub(/^[[:space:]]*-[[:space:]]*/, ""); items = items " " $0; next }
    intest { judge() }
    END { if (intest) judge(); exit found ? 0 : 1 }
  '
}

rule_real_healthcheck() {
  local f
  for f in $(tracked_files 'services/*/compose.yaml'); do
    case "$f" in services/_*) continue ;; esac
    if has_placeholder_probe "$f"; then
      fail "$f" real-healthcheck "placeholder probe from the template — replace with a real check"
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

RULES='rule_doc_reachable rule_symlink_integrity rule_links_resolve rule_real_healthcheck'
for rule in $RULES; do "$rule"; done

if [ "$FAILURES" -gt 0 ]; then
  echo "conventions: $FAILURES violation(s)" >&2
  exit 1
fi
echo "conventions: all checks passed"
