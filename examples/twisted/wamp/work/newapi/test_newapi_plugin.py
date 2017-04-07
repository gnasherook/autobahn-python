from __future__ import print_function
import datetime

from autobahn.twisted.component import Component, run
from twisted.internet import reactor, task
from twisted.internet.defer import (
    Deferred, DeferredList, maybeDeferred, inlineCallbacks,
    CancelledError, returnValue, FirstError, succeed
)
from autobahn.wamp import exception, types
from twisted.logger import Logger

from pluginmixin import PluginMixin


class SimplePubSubExamplePlugin(PluginMixin):
    """
    User-code plugin, Component/session agnostic
    """

    log = Logger()

    plugin_name = u'is_anyone_there'

    def __init__(self, uri_prefix=None, name=None):
        self.session = None
        self.uri_prefix = uri_prefix
        self.plugin_prefix = self.uri_prefix + '.' + self.plugin_name + '.'
        self.name = name

    def subscriptions(self):
        return [
            {
                'uri': u'some.pub...hello',
                'handler': self.heard_someone,
                'options': { 'match': u'wildcard'}
            }
        ]

    @inlineCallbacks
    def publish_greeting(self):
        if not self.session:
            return

        try:
            yield self.session.publish(u'some.pub.' + self.uri_prefix + u'.hello', name=self.name)
        except Exception as e:
            self.log.info('Unable to publish')

    def publish_greeting_loop(self):
        self._greeting = task.LoopingCall(self.publish_greeting)
        self._greeting.start(4, now=True)

    def cancel_greeting_loop(self):
        self._greeting.stop()

    def heard_someone(self, *args, **kwargs):
        self.log.info("{my_name}: {their_name} said hello!", my_name=self.name, their_name=kwargs['name'])

    def on_ready(self):
        self.log.info("PLUGIN {plugin_name} now READY to do some useful stuff...", plugin_name=self.plugin_name)
        self.publish_greeting_loop()

    def on_not_ready(self, flr):
        self.log.info("PLUGIN {plugin_name} NOT READY but I was passed the Failure to see why...", plugin_name=self.plugin_name)

    def on_leave(self):
        self.log.info("PLUGIN {plugin_name} session has been lost, time to do some cleanup operations...", plugin_name=self.plugin_name)
        self.cancel_greeting_loop


class SimpleRPCExamplePlugin(PluginMixin):
    """
    User-code plugin, Component/session agnostic
    """

    log = Logger()

    plugin_name = u'rpc_plugin'

    def __init__(self, uri_prefix=None, name=None, callee_name=None):
        self.session = None
        self.uri_prefix = uri_prefix
        self.plugin_prefix = self.uri_prefix + '.' + self.plugin_name + '.'
        self.name = name
        self.callee_name = callee_name

    def rpcs(self):
        return [
            {
                'uri': self.plugin_prefix + u'system_time',
                'handler': self.utcnow,
                'options': { 'match': u'exact'}
            }
        ]

    def utcnow(self):
        now = datetime.datetime.utcnow()
        system_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            'callee_name': self.name,
            'system_time': system_time
        }

    def setup_remote_call(self):
        reactor.callLater(3, self.get_remote_time)

    @inlineCallbacks
    def get_remote_time(self):
        remote_time = yield self.session.call(u'namespace.' + self.callee_name + u'.' + self.plugin_name + u'.system_time')
        self.log.info("{my_name}: {callee_name}'s system time is {system_time}",
            my_name=self.name,
            callee_name=remote_time['callee_name'],
            system_time=remote_time['system_time']
        )

    def on_ready(self):
        self.log.info("PLUGIN {plugin_name} now READY to do some useful stuff...", plugin_name=self.plugin_name)
        self.setup_remote_call()

    def on_not_ready(self, flr):
        self.log.info("PLUGIN {plugin_name} NOT READY but I was passed the Failure to see why...", plugin_name=self.plugin_name)

    def on_leave(self):
        self.log.info("PLUGIN {plugin_name} session has been lost, time to do some cleanup operations...", plugin_name=self.plugin_name)

class Controller(PluginMixin):
    """
    User-code plugin, Component/session agnostic
    """

    log = Logger()

    plugin_name = u'controller'

    def __init__(self, *args, **kwargs):
        super(Controller, self).__init__(*args, **kwargs)

    def leave_session(self):
        self.session.leave()

    def setup_call(self):
        reactor.callLater(10, self.leave_session)

    def on_ready(self):
        self.log.info("PLUGIN {plugin_name} now READY to do some useful stuff...", plugin_name=self.plugin_name)
        self.setup_call()

    def on_not_ready(self, flr):
        self.log.info("PLUGIN {plugin_name} NOT READY but I was passed the Failure to see why...", plugin_name=self.plugin_name)


bob_plugin1 = SimplePubSubExamplePlugin(uri_prefix=u'namespace.bob', name='bob')
bob_plugin2 = SimpleRPCExamplePlugin(uri_prefix=u'namespace.bob', name='bob', callee_name='alice')
bob_plugin3 = Controller()
alice_plugin1 = SimplePubSubExamplePlugin(uri_prefix=u'namespace.alice', name='alice')
alice_plugin2 = SimpleRPCExamplePlugin(uri_prefix=u'namespace.alice', name='alice', callee_name='bob')
alice_plugin3 = Controller()

bob_plugins = [bob_plugin1, bob_plugin2, bob_plugin3]
alice_plugins = [alice_plugin1, alice_plugin2, alice_plugin3]

bob_component = Component(
    transports=u'ws://localhost:8080/auth_ws',
    realm=u'crossbardemo',
    authentication={
        u"wampcra": {
            "authid": u"username",
            "secret": u"p4ssw0rd",
        }
    },
    plugins=bob_plugins
)

alice_component = Component(
    transports=u'ws://localhost:8080/auth_ws',
    realm=u'crossbardemo',
    authentication={
        u"wampcra": {
            "authid": u"username",
            "secret": u"p4ssw0rd",
        }
    },
    plugins=alice_plugins
)

if __name__ == '__main__':
    run([bob_component, alice_component], log_level='info')
