#/bin/sh
set -x

#work_path=$(dirname $0)
#cd ./${work_path}

WEB_PATH='/root/code/github.com/'
cd $WEB_PATH/pymock
echo "cd to script dir"

function build()
{
  python setup.py bdist_wheel
  mv dist/* ./
  cp -rf ./pymock/res/* ./build/lib/pymock/res/

  build_type=${1}
  echo "build type is $build_type"
  version='test'
  if [ ${build_type} == "PRO" ]; then
    version=`sed '/^VERSION=/!d;s/.*=//' ./version`
  fi

  echo "version is $version" \
  && sed -i "s#ccr.ccs.tencentyun.com/sampsonliu/pymock:\(.*\)#ccr.ccs.tencentyun.com/sampsonliu/pymock:${version}#" build.yml \
  && sed -i "s#BUILD_TYPE:\(.*\)#BUILD_TYPE: ${build_type}#" build.yml \
  && sed -i "s#CODE_VERSION:\(.*\)#CODE_VERSION: ${version}#" build.yml \
  && docker-compose -f build.yml build \
  && docker push ccr.ccs.tencentyun.com/sampsonliu/pymock:${version} \
  && echo "build and push finish"
}

case $1 in
PRO)
  build PRO
  ;;
TEST)
  build TEST
  ;;
*)
  echo "Usage: $(basename $0) {PRO|TEST}"
  exit 1
  ;;
esac
