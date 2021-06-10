#/bin/sh
set -x
work_path=$(dirname $0)
cd ./${work_path}
git branch
git checkout main
git pull
