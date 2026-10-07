#!/usr/bin/env bash
# Bumps the integration's version, tags it and pushes the tag; the Release
# workflow then publishes the GitHub release that HACS installs from.
#
# Usage: ./release.sh <patch|minor|major|X.Y.Z>
set -euo pipefail

cd "$(dirname "$0")"
MANIFEST=custom_components/budgetmanager/manifest.json
BRANCH=master

die() { echo "error: $*" >&2; exit 1; }

[ $# -eq 1 ] || die "usage: $0 <patch|minor|major|X.Y.Z>"

[ "$(git branch --show-current)" = "$BRANCH" ] || die "not on $BRANCH"
[ -z "$(git status --porcelain)" ] || die "the working tree has uncommitted changes"
git fetch --quiet --tags origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$BRANCH")" ] \
    || die "$BRANCH differs from origin/$BRANCH; pull or push first"

current=$(sed -n 's/^ *"version": *"\([0-9]*\.[0-9]*\.[0-9]*\)".*/\1/p' "$MANIFEST")
[ -n "$current" ] || die "no X.Y.Z version in $MANIFEST"
IFS=. read -r major minor patch <<< "$current"

case "$1" in
    patch) version="$major.$minor.$((patch + 1))" ;;
    minor) version="$major.$((minor + 1)).0" ;;
    major) version="$((major + 1)).0.0" ;;
    *)
        [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "not a version: $1"
        version="$1" ;;
esac
tag="v$version"
git rev-parse -q --verify "refs/tags/$tag" >/dev/null && die "$tag already exists"

echo "Changes since ${current}:"
git log --oneline "v$current..HEAD" 2>/dev/null || git log --oneline
echo
read -r -p "Release $current -> $version as $tag and push? [y/N] " answer
[ "$answer" = "y" ] || [ "$answer" = "Y" ] || die "aborted"

if [ "$version" != "$current" ]; then
    sed -i "s/\"version\": *\"$current\"/\"version\": \"$version\"/" "$MANIFEST"
    git add "$MANIFEST"
    git commit --quiet -m "Release $tag"
fi
git tag -a "$tag" -m "Release $tag"
git push --atomic origin "$BRANCH" "$tag"

echo "Pushed $tag; the Release workflow will publish it:"
echo "https://github.com/Adrian94F/BudgetManager-HA/actions/workflows/release.yml"
