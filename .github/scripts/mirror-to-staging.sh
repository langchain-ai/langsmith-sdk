#!/usr/bin/env bash
# Rewrite one langsmith-sdk commit for a staging repo and apply it with git apply --3way.
# Usage: mirror-to-staging.sh <python|js> <sha> <staging-checkout> [out-dir]
# Run from the langsmith-sdk checkout. Writes summary.md + status (clean|conflict|noop) to out-dir.
set -euo pipefail
lang=$1 sha=$2 staging=$(cd "$3" && pwd) out=${4:-$(mktemp -d)}
mkdir -p "$out"

case $lang in
  python)
    root=python gen=python/langsmith/_openapi_client
    mapped='python/langsmith/|python/tests/|python/bench/'
    # header lines only: python/langsmith -> src/langsmith, python/tests -> tests, python/bench -> bench
    paths='s#(^| |/)python/langsmith/#\1src/langsmith/#g; s#(^| |/)python/(tests|bench)/#\1\2/#g'
    text='s/langsmith\._openapi_client/langsmith/g'
    ;;
  js)
    root=js gen=js/src/_openapi_client
    mapped='js/src/'
    paths='s#(^| |/)js/src/#\1src/lib/#g'
    # generated client sits one level above src/lib; its index is client.ts there
    text='s#"\.\./_openapi_client/index\.js"#"../../client.js"#g; s#"\./_openapi_client/index\.js"#"../client.js"#g; s#"\.\./_openapi_client/#"../../#g; s#"\./_openapi_client/#"../#g'
    ;;
  *) echo "lang must be python or js" >&2; exit 2 ;;
esac

rewrite=() dropped=() manual=()
while IFS= read -r f; do
  if [[ $f == $gen/* ]]; then dropped+=("$f")
  elif [[ $f =~ ^($mapped) ]]; then rewrite+=("$f")
  else manual+=("$f")
  fi
done < <(git diff --name-only "$sha^" "$sha" -- "$root")

list() { if (($#)); then printf -- '- `%s`\n' "$@"; else echo "- none"; fi; }

if ((${#rewrite[@]} == 0)); then
  { echo "## Dropped (generated client, synced separately)"; list ${dropped[@]+"${dropped[@]}"}
    echo; echo "## Needs manual port"; list ${manual[@]+"${manual[@]}"}; } > "$out/summary.md"
  echo noop > "$out/status"; exit 0
fi

git diff --binary --full-index "$sha^" "$sha" -- "${rewrite[@]}" \
  | sed -E "/^(diff --git |--- |\+\+\+ |rename (from|to) |copy (from|to) )/ { $paths; }" \
  | sed -E "$text" > "$out/$lang.patch"

# --3way needs the preimage blobs in the target repo, rewritten like the patch so the index hashes match
for f in "${rewrite[@]}"; do
  old=$(git rev-parse -q --verify "$sha^:$f" 2>/dev/null) || continue
  new=$(git cat-file blob "$old" | sed -E "$text" | git -C "$staging" hash-object -w --stdin)
  [[ $old == "$new" ]] || sed -i.bak "s/^index $old\.\./index $new../" "$out/$lang.patch"
done
rm -f "$out/$lang.patch.bak"

# apply per file so one unmergeable file does not abort the rest
awk -v o="$out" '/^diff --git /{n++} {print > sprintf("%s/chunk-%03d", o, n)}' "$out/$lang.patch"
failed=()
for c in "$out"/chunk-*; do
  before=$(git -C "$staging" diff --name-only --diff-filter=U | wc -l)
  if ! git -C "$staging" apply --3way "$c" 2>>"$out/apply.log"; then
    after=$(git -C "$staging" diff --name-only --diff-filter=U | wc -l)
    ((after > before)) || failed+=("$(sed -nE 's#^diff --git a/(.*) b/.*#\1#p;q' "$c")")
  fi
done
conflicts=()
while IFS= read -r f; do [[ -n $f ]] && conflicts+=("$f"); done < <(git -C "$staging" diff --name-only --diff-filter=U)

{
  echo "## Rewritten"; list ${rewrite[@]+"${rewrite[@]}"}
  echo; echo "## Dropped (generated client, synced separately)"; list ${dropped[@]+"${dropped[@]}"}
  echo; echo "## Needs manual port"; list ${manual[@]+"${manual[@]}"}
  if ((${#conflicts[@]})); then echo; echo "## Conflicts (markers left in place)"; list ${conflicts[@]+"${conflicts[@]}"}; fi
  if ((${#failed[@]})); then echo; echo "## Failed to apply (see $lang.patch in the workflow artifact)"; list ${failed[@]+"${failed[@]}"}; fi
} > "$out/summary.md"

if ((${#conflicts[@]} + ${#failed[@]})); then echo conflict > "$out/status"
elif git -C "$staging" diff --quiet HEAD; then echo noop > "$out/status"
else echo clean > "$out/status"
fi
