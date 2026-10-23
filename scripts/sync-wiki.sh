#!/usr/bin/env bash
# Push the in-repo wiki/ pages to the GitHub Wiki (GRAAL_Analysis.wiki.git).
# Usage: scripts/sync-wiki.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WIKI_SRC="$REPO_ROOT/wiki"
WIKI_REMOTE="${WIKI_REMOTE:-https://github.com/AntoninoFulci/GRAAL_Analysis.wiki.git}"

shopt -s nullglob
WIKI_PAGES=("${WIKI_SRC}"/*.md)
if [[ ${#WIKI_PAGES[@]} -eq 0 ]]; then
  echo "ERROR: no Markdown pages found in ${WIKI_SRC}" >&2
  exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Git supports cloning an empty local/remote repository. Authentication and
# network failures must stop here, never masquerade as an empty wiki.
git clone "$WIKI_REMOTE" "$WORK/wiki"
cd "$WORK/wiki"

if git show-ref --verify --quiet refs/remotes/origin/master; then
  git checkout -q -B master origin/master
else
  git branch -M master
fi

# Replace all pages so deletions in wiki/ propagate and stale remote pages are
# pruned. WIKI_PAGES was validated before any remote interaction.
git rm -q -- '*.md' 2>/dev/null || true
cp "${WIKI_PAGES[@]}" .
git add -A
if git diff --cached --quiet; then
  echo "Wiki already up to date."
  exit 0
fi

git commit -q -m "docs: sync wiki from main repo"
git push -u origin master
echo "Wiki pushed."
