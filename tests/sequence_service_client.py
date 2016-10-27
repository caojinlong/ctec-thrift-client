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

smsid_thrift = thriftpy.load("sequence_service.thrift", module_name="sequence_thrift")

xiaohao_smsid_service_client = ClientPool(server_hosts=['10.128.89.30:9915'],
                                          service=smsid_thrift.SequenceService,
                                          max_renew_times=3,
                                          maxActive=20,
                                          maxIdle=10,
                                          get_connection_timeout=10,
                                          socket_timeout=60)

app = Flask(__name__)


@app.route("/thrift", methods=['GET'])
def sequence_service():
    """
    测试序列服务
    :return:
    """
    res_body = None
    try:
        res = xiaohao_smsid_service_client.getSequence(5)
        res_body = {'res': res}
    except Exception, ex:
        print ex.message
    finally:
        pass
    return jsonify(res_body)


if __name__ == "__main__":
    http_server = WSGIServer(('127.0.0.1', 8000), app, log=None)
    http_server.serve_forever()
