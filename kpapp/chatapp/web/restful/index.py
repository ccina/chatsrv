# -*- coding:utf-8 -*-
from __future__ import print_function
import tornado

from tornado import gen
from kpages import url, ContextHandler, LogicContext, get_context, service_async

import tornado.httpserver
import tornado.web
import tornado.websocket
import tornado.ioloop
import pdb, json, os, redis

import tornadoredis


c = tornadoredis.Client()
c.connect()


@url(r"/")
class IndexHandler(ContextHandler, tornado.web.RequestHandler):
    def get(self):
        self.render("chat.html")

@url(r"/pullMsg")
class MessageHandler(ContextHandler, tornado.websocket.WebSocketHandler):
    def __init__(self, *args, **kwargs):
        super(MessageHandler, self).__init__(*args, **kwargs)
        self.uid = False

    @gen.engine
    def listen(self, uid_ch):
        self.client = tornadoredis.Client()
        self.client.connect()
        yield gen.Task(self.client.subscribe, uid_ch)
        self.client.listen(self.on_message)

    def on_message(self, msg):
        #pdb.set_trace()
        if hasattr(msg, "kind"):
            if msg.kind == 'message':
                self.write_message(str(msg.body))
            if msg.kind == 'disconnect':
                self.write_message('The connection terminated '
                                   'due to a Redis server error.')
                self.close()
        else:
            msg = json.loads(msg)
            if msg.get("type", None) == "auth" and not self.uid:
                uid = msg.get("uid", None)
                if uid:
                    with LogicContext():
                        r = get_context().get_redis()
                        res = r.sadd("curusrs", uid)
                        if res:
                            self.uid = uid
                            self.listen(uid)
                            bc(r, json.dumps({"type":"contactref","uid":uid, "action":"add"}))
                            self.write_message(json.dumps({"type":"authstat", "stat":1}))
                            bcm(r, self)
                            return
                self.write_message(json.dumps({"type":"authstat", "stat":0}))
            elif msg.get("type", None) == "msg" and self.uid:
                tousr = msg.get("to", None)
                msgtxt = msg.get("msg", None)
                if tousr and msgtxt:
                    with LogicContext():
                        r = get_context().get_redis()
                        res = r.sismember("curusrs", tousr)
                        if res:
                            c.publish(tousr, json.dumps({"type":"msg", "from":self.uid, "msg":msgtxt}))
                            self.write_message(json.dumps({"stat":1}))
                            return
                self.write_message(json.dumps({"stat":0}))


    def on_close(self):
        if self.client.subscribed:
            with LogicContext():
                r = get_context().get_redis()
                r.srem("curusrs", self.uid)
                bc(r, json.dumps({"type":"contactref","uid":self.uid, "action":"rm"}))
                self.client.unsubscribe(self.uid)
                self.client.disconnect()


def bc(r, msg):
    curusrs = r.smembers("curusrs")
    for e in curusrs:
        c.publish(e, msg)

def bcm(r, m):
    curusrs = r.smembers("curusrs")
    for e in curusrs:
        m.write_message(json.dumps({"type":"contactref","uid":e, "action":"add"}))
