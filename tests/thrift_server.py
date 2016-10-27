# coding: utf-8

import thriftpy
from thriftpy.rpc import make_server

sequence_thrift = thriftpy.load("sequence.thrift", module_name="sequence_thrift")


class GetSequenceService(object):

    def getnum(self, req):
        """
        返回请求的数串
        :param req:
        :return:
        """
        res = sequence_thrift.SequenceResponse()
        res.num = req.num
        print req.num
        return res


server = make_server(sequence_thrift.Sequence, GetSequenceService(), '127.0.0.1', 6001)

server.serve()
