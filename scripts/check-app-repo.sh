#!/usr/bin/env bash
# Checks that an app repository matches the onboarding answers before anything
# is rendered for it: each component's folder (layout folders) or the repository
# root (layout root) exists, has a package.json and the lockfile of the chosen
# package manager. Catches the most common form slip (npm chosen, yarn.lock in
# the repo), which otherwise fails the first pipeline run in three places.
# Usage: check-app-repo.sh <owner/repo> <answers.json>
# Needs GH_TOKEN able to read the repository. Exit 1 with the problems listed.
set -euo pipefail
repository=$1 answers=$2
pm=$(jq -r .package_manager "$answers")
layout=$(jq -r '.layout // "folders"' "$answers")
case "$pm" in yarn) lock=yarn.lock; other=package-lock.json ;; *) lock=package-lock.json; other=yarn.lock ;; esac
problems=()
for component in backend frontend; do
  [ "$(jq -r ".$component" "$answers")" != "not-needed" ] || continue
  if [ "$layout" = root ]; then path=""; where="the root of $repository"; else path="$component/"; where="\`$component/\` in $repository"; fi
  if ! names=$(gh api "repos/$repository/contents/$path" --jq '.[].name' 2>/dev/null); then
    problems+=("$where not found")
    continue
  fi
  grep -qx package.json <<<"$names" || problems+=("\`${path}package.json\` missing in $repository")
  if ! grep -qx "$lock" <<<"$names"; then
    hint=""
    grep -qx "$other" <<<"$names" && hint=" (it has \`$other\`: choose the other package manager, or switch the app)"
    problems+=("\`${path}$lock\` missing in $repository, but package manager \`$pm\` was chosen$hint")
  fi
done
if [ ${#problems[@]} -gt 0 ]; then
  printf '%s\n' "${problems[@]}"
  exit 1
fi
echo "$repository matches the answers (layout $layout, package manager $pm)"
