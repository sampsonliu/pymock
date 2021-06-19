#! /bin/bash
set -x
work_path=$(dirname $0)
cd ./${work_path}
echo "cd to script dir"

sh build-test.sh
