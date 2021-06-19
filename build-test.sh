#/bin/sh
set -x
work_path=$(dirname $0)
cd ./${work_path}
echo "cd to script dir"

sh pull-code.sh
sh build.sh TEST
