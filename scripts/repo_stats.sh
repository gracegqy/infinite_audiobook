#!/bin/zsh
# Derivation script for every repo-scale number quoted outward (README.md,
# applications, résumé lines). Exists because NUMBERS_PROTOCOL G1 requires a
# COMMITTED script that reproduces the figure from on-disk artifacts — a number
# computed in a session snippet is unauditable and cannot be re-run later.
#
#   bash scripts/repo_stats.sh
#
# Copy figures from this output. Never retype one, never quote one from a doc
# that quotes it. Ledger: docs/REPORTABLE_NUMBERS.md.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "as-of-commit:      $(git rev-parse --short HEAD)"
echo "as-of-date:        $(date +%Y-%m-%d)"
echo "clean-worktree:    $([[ -z "$(git status --porcelain)" ]] && echo yes || echo 'NO — figures describe uncommitted state')"
echo

# Grain: files tracked by git at HEAD. Excludes data/, .venv/, node_modules/,
# dist/ (all gitignored), so this is the repo as a reader clones it. Binary
# icons are excluded from the line total — `wc -l` over a PNG is noise, not
# lines (the extension-scoped figures below never counted them).
echo "tracked-files:     $(git ls-files | wc -l | tr -d ' ')"
echo "tracked-lines-all: $(git ls-files | grep -vE '\.png$' | xargs wc -l | tail -1 | awk '{print $1}')"
echo

# Source vs prose, split because "LOC" that silently includes a 1,800-line
# JOURNAL is not a code-size claim. Source = what runs.
py=$(git ls-files '*.py' | xargs wc -l | tail -1 | awk '{print $1}')
web=$(git ls-files '*.ts' '*.tsx' '*.jsx' '*.css' '*.html' | xargs wc -l | tail -1 | awk '{print $1}')
sh=$(git ls-files '*.sh' | xargs wc -l | tail -1 | awk '{print $1}')
md=$(git ls-files '*.md' | xargs wc -l | tail -1 | awk '{print $1}')
echo "source-lines-py:   $py   ($(git ls-files '*.py' | wc -l | tr -d ' ') files)"
echo "source-lines-web:  $web   ($(git ls-files '*.ts' '*.tsx' '*.jsx' '*.css' '*.html' | wc -l | tr -d ' ') files)"
echo "source-lines-sh:   $sh   ($(git ls-files '*.sh' | wc -l | tr -d ' ') files)"
echo "source-lines-total:$(( py + web + sh ))"
echo "prose-lines-md:    $md   (governance + design docs; NOT source)"
echo

# pre_design_probes/ is throwaway with no authority after Phase 1 (CLAUDE.md).
# Counted with the SAME extension list as source-lines-total above, so this
# figure subtracts from that one exactly — a probe count that used a narrower
# glob would not reconcile, which is how ledger rows go wrong.
probe=$(git ls-files 'pre_design_probes/*.py' 'pre_design_probes/*.jsx' \
        'pre_design_probes/*.css' 'pre_design_probes/*.html' 'pre_design_probes/*.sh' \
        | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
echo "of-which-probes:   ${probe:-0}   (subtract for a 'source I stand behind' claim)"
echo "test-lines:        $(git ls-files 'tests/*.py' | xargs wc -l | tail -1 | awk '{print $1}')"
echo

if [[ -x .venv/bin/python ]]; then
  echo "tests-collected:   $(.venv/bin/python -m pytest --collect-only -q 2>/dev/null | tail -1)"
else
  echo "tests-collected:   SKIPPED (no .venv — run from the project venv)"
fi
echo

# The content-rights claim in README.md. Must print nothing, ever.
leaked=$(git log --all --diff-filter=A --name-only --pretty=format: \
         | sort -u | grep -E '^(data/|\.env)' || true)
if [[ -z "$leaked" ]]; then
  echo "never-committed:   CONFIRMED — no data/ or .env path was ever added in any commit on any branch"
else
  echo "never-committed:   *** FAILED *** the following were committed at some point:"
  echo "$leaked"
  exit 1
fi
