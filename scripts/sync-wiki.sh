#!/usr/bin/env bash
# Push the in-repo wiki/ pages to the GitHub Wiki (GRAAL_Analysis.wiki.git).
# Usage: scripts/sync-wiki.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WIKI_SRC="$REPO_ROOT/wiki"
WIKI_REMOTE="https://github.com/AntoninoFulci/GRAAL_Analysis.wiki.git"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Clone the wiki if it has pages; otherwise start an empty checkout. A brand-new
# wiki with no pages cannot be cloned — that legitimately falls through to init.
# Clone errors (auth/network) are shown, not hidden, so a masked failure does not
# silently become a rejected push.
if git clone "$WIKI_REMOTE" "$WORK/wiki"; then
  cd "$WORK/wiki"
else
  echo "Clone failed (empty wiki or unreachable) — starting a fresh checkout." >&2
  mkdir -p "$WORK/wiki"
  cd "$WORK/wiki"
  git init -q
  git branch -M master
  git remote add origin "$WIKI_REMOTE"
fi

# Replace all pages so deletions in wiki/ propagate (stale wiki pages are pruned).
git rm -q -- '*.md' 2>/dev/null || true
cp "$WIKI_SRC"/*.md .
git add -A
if git diff --cached --quiet; then
  echo "Wiki already up to date."
  exit 0
fi
git commit -q -m "docs: sync wiki from main repo"
git push -u origin master
echo "Wiki pushed."
