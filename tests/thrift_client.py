# coding: utf-8

import thriftpy
import sys
from flask import request, jsonify
from flask import Flask
from gevent.wsgi import WSGIServer
from ctec_thrift_client.client_pool import ClientPool
from gevent import monkey

reload(sys)

monkey.patch_all()

sequence_thrift = thriftpy.load("sequence.thrift", module_name="sequence_thrift")

client_pool_sequence = ClientPool(server_hosts=["127.0.0.1:6000"],
                                  service=sequence_thrift.Sequence,
                                  max_renew_times=3,
                                  maxActive=3,
                                  maxIdle=2,
                                  get_connection_timeout=10,
                                  socket_timeout=30)

client_pool_sequence_with_zookeeper = ClientPool(zk_hosts="172.16.50.146:8581",
                                                 zk_path="/thrift",
                                                 service=sequence_thrift.Sequence,
                                                 max_renew_times=3,
                                                 maxActive=3,
                                                 maxIdle=2,
                                                 get_connection_timeout=10,
                                                 socket_timeout=30)

app = Flask(__name__)


@app.route("/thrift", methods=['GET'])
def sequence_service():
    """
    测试返回的序列是否乱序
    :return:
    """
    res_body = None
    try:
        data = request.args.get('num', '')
        req = sequence_thrift.SequenceRequest()
        if data:
            req.num = str(data)
            res = client_pool_sequence_with_zookeeper.getnum(req)
            print "Request:" + req.num + "   " + "Response:" + res.num
            res_body = {'req': req.num, 'res': res.num}
    except Exception, ex:
        print ex.message
    finally:
        pass
    return jsonify(res_body)


if __name__ == "__main__":
    http_server = WSGIServer(('127.0.0.1', 8000), app, log=None)
    http_server.serve_forever()
