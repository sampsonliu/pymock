#/bin/sh
set -x
echo "cd to script dir"
work_path=$(dirname $0)
cd ./${work_path}

sh build.sh TEST
