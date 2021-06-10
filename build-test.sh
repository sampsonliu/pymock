#/bin/sh
set -x

echo "start deployment"
WEB_PATH='/root/code/github.com/'
cd $WEB_PATH/pymock
echo "cd to script dir"
echo "fetching from remote..."
# 为了避免冲突，强制更新本地文件
git fetch --all
git reset --hard origin/main
echo "done"

sh build.sh TEST
