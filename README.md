# 中国电信电子渠道运营中心 Thrift RPC 客户端

## 环境

`Python2` 或 `Python3`

- `kazoo`
- `thriftpy`

## 使用
- server_hosts:服务端地址，数组类型，['ip:port','ip:port']
- service:thrift service名称
- max_renew_times:连接断开后重连的次数，请设置为>=2
- maxActive:最大连接数
- maxIdle:最大空闲连接数
- get_connection_timeout:获取连接的超时时间
- socket_timeout:读取数据的超时时间
- client_pool = ClientPool(server_hosts=["127.0.0.1:6000"],
                               service=sequencetest_thrift.Sequence,
                               max_renew_times=3,
                               maxActive=3,
                               maxIdle=2,
                               get_connection_timeout = 10,
                               socket_timeout = 30)

- 调用时，与版本1.0.4的区别是直接client_pool.method(),其中method为thrift文件中定义的方法，不需要获取client连接

## FAQ