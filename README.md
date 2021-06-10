### 构建并推送镜像到腾讯云-容器服务-个人仓库 ###
```
sh build-test.sh
```

### 启动服务 ###
```
sh start-test.sh
```

### generate server certificate ###
```
openssl genrsa -out server.key 2048
openssl req -new -x509 -key server.key -out server.crt
```
