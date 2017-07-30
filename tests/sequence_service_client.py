# coding: utf-8

import thriftpy
import sys
from flask import request, jsonify
from flask import Flask
from gevent.wsgi import WSGIServer
from ctec_thrift_client.client_pool import ClientPool
from gevent import monkey
import datetime

reload(sys)

monkey.patch_all()

smsid_thrift = thriftpy.load("sequence_service.thrift", module_name="sequence_thrift")

xiaohao_smsid_service_client = ClientPool(server_hosts=['172.16.20.46:9915'],
                                          service=smsid_thrift.SequenceService,
                                          max_renew_times=3,
                                          maxActive=20,
                                          maxIdle=10,
                                          get_connection_timeout=10,
                                          socket_timeout=60)

app = Flask(__name__)

seq_list = []

@app.route("/health_check", methods=['GET'])
def sequence_service():
    """
    测试序列服务
    :return:
    """
    res_body = None
    try:
        res = xiaohao_smsid_service_client.getSequence(1)
        if res is not None:
            res = ''.join(['10000000834', datetime.datetime.now().strftime("%Y%m%d"), str(res).rjust(9, '0')])
            print res
        # if res in seq_list:
        #     print "***********************************************"
        #     print res
        # else:
        #     seq_list.append(res)
        res_body = {'res': res}
    except Exception, ex:
        print ex.message
    finally:
        pass
    return jsonify(res_body)


if __name__ == "__main__":
    http_server = WSGIServer(('127.0.0.1', 8088), app, log=None)
    http_server.serve_forever()
