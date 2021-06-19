#/bin/sh
set -x

work_path=$(dirname $0)
cd ./${work_path}
echo "cd to script dir"

docker-compose -f test.yml down && docker-compose -f test.yml up -d
