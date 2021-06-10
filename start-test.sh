#/bin/sh
set -x
echo "cd to script dir"
work_path=$(dirname $0)
cd ./${work_path}

docker-compose -f test.yml down && docker-compose -f test.yml up -d
