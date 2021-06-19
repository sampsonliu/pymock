#! /bin/bash
set -x

git reset --hard origin/main
git clean -f
git pull
git checkout main
