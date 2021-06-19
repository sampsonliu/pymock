#! /bin/bash
set -x
work_path=$(dirname $0)
cd ./${work_path}
echo "cd to script dir"

git reset --hard origin/main
git clean -f
git pull
git checkout main
