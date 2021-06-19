#/bin/sh
set -x
work_path=$(dirname $0)
cd ./${work_path}
echo "cd to script dir"

git add .
git commit -m '更新'
git pull
git push
