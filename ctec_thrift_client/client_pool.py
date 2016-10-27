# coding: utf-8

import threading
from collections import deque
import logging
import socket

from kazoo.client import KazooClient
from thriftpy.protocol import TBinaryProtocolFactory
from thriftpy.transport import (
    TBufferedTransportFactory,
    TSocket,
)
from gevent.event import AsyncResult
from gevent import Timeout

from error import CTECThriftClientError
from thriftpy.thrift import TClient
from thriftpy.transport import TTransportException


class ClientPool:
    def __init__(self, service, server_hosts=None, zk_path=None, zk_hosts=None, max_renew_times=3, maxActive=20,
                 maxIdle=10, get_connection_timeout=30, socket_timeout=30):
        """
        :param service: Thrift的Service名称
        :param server_hosts: 服务提供者地址，数组类型，['ip:port','ip:port']
        :param zk_path: 服务提供者在zookeeper中的路径
        :param zk_hosts: zookeeper的host地址，多个请用逗号隔开
        :param max_renew_times: 最大重连次数
        :param maxActive: 最大连接数
        :param maxIdle: 最大空闲连接数
        :param get_connection_timeout:获取连接的超时时间
        :param socket_timeout: 读取数据的超时时间
        """
        # 负载均衡队列
        self.load_balance_queue = deque()
        self.service = service
        self.lock = threading.RLock()
        self.max_renew_times = max_renew_times
        self.maxActive = maxActive
        self.maxIdle = maxIdle
        self.connections = set()
        self.pool_size = 0
        self.get_connection_timeout = get_connection_timeout
        self.no_client_queue = deque()
        self.socket_timeout = socket_timeout

        if zk_hosts:
            self.kazoo_client = KazooClient(hosts=zk_hosts)
            self.kazoo_client.start()
            self.zk_path = zk_path
            self.zk_hosts = zk_hosts
            # 定义Watcher
            self.kazoo_client.ChildrenWatch(path=self.zk_path,
                                            func=self.watcher)
            # 刷新连接池中的连接对象
            self.__refresh_thrift_connections(self.kazoo_client.get_children(self.zk_path))
        elif server_hosts:
            self.server_hosts = server_hosts
            # 复制新的IP地址到负载均衡队列中
            self.load_balance_queue.extendleft(self.server_hosts)
        else:
            raise CTECThriftClientError('没有指定服务器获取方式！')

    def get_new_client(self):
        """
        轮询在每个ip:port的连接池中获取连接（线程安全）
        从当前队列右侧取出ip:port信息，获取client
        将连接池对象放回到当前队列的左侧
        请求或连接超时时间，默认30秒
        :return:
        """
        with self.lock:
            if self.pool_size < self.maxActive:
                try:
                    ip = self.load_balance_queue.pop()
                except IndexError:
                    raise CTECThriftClientError('没有可用的服务提供者列表！')
                if ip:
                    self.load_balance_queue.appendleft(ip)
                    # 创建新的thrift client
                    t_socket = TSocket(ip.split(':')[0], int(ip.split(':')[1]),
                                       socket_timeout=1000 * self.socket_timeout)
                    proto_factory = TBinaryProtocolFactory()
                    trans_factory = TBufferedTransportFactory()
                    transport = trans_factory.get_transport(t_socket)
                    protocol = proto_factory.get_protocol(transport)
                    transport.open()
                    client = TClient(self.service, protocol)
                    self.pool_size += 1
                return client
            else:
                return None

    def close(self):
        """
        关闭所有连接池和zk客户端
        :return:
        """
        if getattr(self, 'kazoo_client', None):
            self.kazoo_client.stop()

    def watcher(self, children):
        """
        zk的watcher方法，负责检测zk的变化，刷新当前双端队列中的连接池
        :param children: 子节点，即服务提供方的列表
        :return:
        """
        self.__refresh_thrift_connections(children)

    def __refresh_thrift_connections(self, children):
        """
        刷新服务提供者在当前队列中的连接池信息（线程安全），主要用于zk刷新
        :param children:
        :return:
        """
        print children
        with self.lock:
            # 清空负载均衡队列
            self.load_balance_queue.clear()
            # 清空连接池
            self.connections.clear()
            # 复制新的IP地址到负载均衡队列中
            self.load_balance_queue.extendleft(children)

    def __getattr__(self, name):
        """
        函数调用，最大重试次数为max_renew_times
        :param name:
        :return:
        """

        def method(*args, **kwds):

            # 从连接池获取连接
            client = self.get_client_from_pool()

            # 连接池中无连接
            if client is None:
                # 设置获取连接的超时时间
                time_out = Timeout(self.get_connection_timeout)
                time_out.start()
                try:
                    async_result = AsyncResult()
                    self.no_client_queue.appendleft(async_result)
                    client = async_result.get()  # blocking
                except:
                    self.no_client_queue.remove(async_result)
                    logging.error("Get Connection Timeout!")
                finally:
                    time_out.cancel()

            if client is not None:

                for i in xrange(self.max_renew_times):
                    try:
                        put_back_flag = True
                        fun = getattr(client, name, None)
                        return fun(*args, **kwds)
                    except socket.timeout:
                        logging.error("Socket Timeout!")
                        # 关闭连接，不关闭会导致乱序
                        put_back_flag = False
                        self.close_one_client(client)
                        break

                    except TTransportException, e:
                        put_back_flag = False

                        if e.type == TTransportException.END_OF_FILE:
                            logging.warning("Socket Connection Reset Error!")
                            with self.lock:
                                client.close()
                                self.pool_size -= 1
                                client = self.get_new_client()
                        else:
                            logging.error("Socket Error!")
                            self.close_one_client(client)
                            break

                    except socket.error, e:
                        put_back_flag = False
                        if e.errno == socket.errno.ECONNABORTED:
                            logging.warning("Socket Connection aborted Error!")
                            with self.lock:
                                client.close()
                                self.pool_size -= 1
                                client = self.get_new_client()
                        else:
                            logging.error("Socket Error!")
                            self.close_one_client(client)
                            break
                    finally:
                        # 将连接放回连接池
                        if put_back_flag is True:
                            self.put_back_connections(client)
            return None

        return method

    def close_one_client(self, client):
        """
        线程安全
        关闭连接
        :param client:
        :return:
        """
        with self.lock:
            client.close()
            self.pool_size -= 1

    def put_back_connections(self, client):
        """
        线程安全
        将连接放回连接池，逻辑如下：
        1、如果有请求尚未获取到连接，请求优先
        2、如果连接池中的连接的数目小于maxIdle，则将该连接放回连接池
        3、关闭连接
        :param client:
        :return:
        """
        with self.lock:
            if self.no_client_queue.__len__() > 0:
                task = self.no_client_queue.pop()
                task.set(client)
            elif self.connections.__len__() < self.maxIdle:
                self.connections.add(client)
            else:
                client.close()
                self.pool_size -= 1

    def get_client_from_pool(self):
        """
        线程安全
        从连接池中获取连接，若连接池中有连接，直接取出，否则，
        新建一个连接，若一直无法获取连接，则返回None
        :return:
        """

        client = self.get_one_client_from_pool()
        if client is not None:
            return client

        client = self.get_new_client()
        if client is not None:
            return client

        return None

    def get_one_client_from_pool(self):
        """
        线程安全
        从连接池中获取一个连接，若取不到连接，则返回None
        :return:
        """
        with self.lock:
            if self.connections:
                try:
                    return self.connections.pop()
                except KeyError:
                    return None
            return None
