#!/usr/bin/env bash
# Mirror every langsmith-sdk commit in from..to onto the staging checkout, one commit each.
# Usage: mirror-since.sh <python|js> <to-sha> <staging-checkout> <out-dir>
# Starts after the sha in staging/.mirror-source (or at to-sha^ if missing). Writes status + body.md to out-dir.
set -euo pipefail
lang=$1 to=$2 staging=$(cd "$3" && pwd) out=$4
mkdir -p "$out"; out=$(cd "$out" && pwd); : > "$out/body.md"
root=python; [[ $lang == js ]] && root=js
here=$(dirname "$0")

from=$(cat "$staging/.mirror-source" 2>/dev/null || true)
git rev-parse -q --verify "${from:-x}^{commit}" >/dev/null 2>&1 || from="$to^"

status=noop
for c in $(git rev-list --reverse --first-parent "$from..$to" -- "$root"); do
  author=$(git log -1 --format=%an "$c"); subject=$(git log -1 --format=%s "$c")
  if [[ $author == "langtions-bot[bot]" || $subject == release\(* ]]; then
    echo "- skipped: $subject" >> "$out/body.md"; continue
  fi
  "$here/mirror-to-staging.sh" "$lang" "$c" "$staging" "$out/$c"
  st=$(cat "$out/$c/status")
  case $st in
    clean|conflict)
      echo "$c" > "$staging/.mirror-source"
      git -C "$staging" add -A
      git -C "$staging" commit -q --author="$(git log -1 --format='%an <%ae>' "$c")" \
        -m "$subject" -m "Mirrored from langchain-ai/langsmith-sdk@$c"
      [[ $st == conflict || $status == conflict ]] && status=conflict || status=clean ;;
    manual) [[ $status == noop ]] && status=manual ;;
  esac
  { echo "### $subject (langchain-ai/langsmith-sdk@${c:0:8}): $st"; cat "$out/$c/summary.md"; echo; } >> "$out/body.md"
done
echo "$status" > "$out/status"
