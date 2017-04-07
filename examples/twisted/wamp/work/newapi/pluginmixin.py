from twisted.internet.defer import (
    Deferred, DeferredList
)
from autobahn.wamp import types
from twisted.internet import reactor

class PluginMixin(object):

    """
    Base mixin class for a plugin - to be included in AB public API
    """

    def _on_session_join(self, session, details):
        """
        Called from Component's on_join event handler
        """
        self.session = session

        def err(flr):
            self.log.info("REGISTRATION: router registrations for {name} FAILED", name=self.plugin_name)
            flr.printTraceback()
            reactor.callLater(0, self.on_not_ready, flr)

        d = Deferred()
        d.addCallback(lambda res: self.on_join(details))
        d.addCallback(self._register_rpcs)
        d.addCallback(self._register_subscriptions)
        d.addCallback(lambda res: reactor.callLater(0, self.on_ready))
        d.addErrback(err)
        d.callback(True)

    def _on_session_leave(self, session, details):
        """
        Called from Component's on_leave event handler
        """
        self.session = None
        self.on_leave()

    def on_join(self, details):
        """
        Override in subclass if needed
        Session joined but no registrations have taken place yet
        A deferred can be returned if async operations are required.
        """
        pass

    def on_leave(self):
        """
        Override in subclass if needed
        """
        pass

    def on_ready(self):
        """
        Override in subclass if needed
        Called when the session has been joined and all RPCs/Subscriptions to the router have completed
        (or a session has resumed with previous subscriptions auto restored?)
        """
        pass

    def on_not_ready(self, flr):
        """
        Override in subclass if needed
        Called when there was a problem with this plugin's router subscriptions
        """
        pass


    def subscriptions(self):
        """
        Override in subclass if needed
        Return dictionary of publications to subscribe to
        """
        return None

    def rpcs(self):
        """
        Override in subclass if needed
        Return dictionary of RPCs to register with the router
        """
        return None

    def _register_subscriptions(self, res):
        if not self.subscriptions():
            return None

        d_reg = self._router_registrations(
            reg_type='subscription', registrations=self.subscriptions()
        )

        return d_reg

    def _register_rpcs(self, res):
        if not self.rpcs():
            return None

        d_reg = self._router_registrations(
            reg_type='rpc', registrations=self.rpcs()
        )

        return d_reg

    ###############################
    # ROUTER REGISTRATIONS ########
    ###############################
    def _router_registrations(self, reg_type=None, registrations=None):
        """
        Handles registering RPCs and subscribing to topics
        reg_type should be 'subscription' or 'rpc'
        registrations is a dict with 'uri', 'handler' and optional 'options' keys
        Returns a deferred
       """

        def registrations_succeeded(results):
            """
            dlist callback
            """
            d_caller.callback(None)

        def registrations_failed(flr, d_caller):
            """
            dlist errback. Called on the first registrations failing.
            """
            cancel_registration_deferreds()
            d_caller.errback(flr)

        def cancel_registration_deferreds():
            """
            No point in continuing with more registrations as reconnection
            is about to happen so cancel them
            """
            for d in registration_list:
                d.cancel()

        def make_register_options(options):
            return types.RegisterOptions(**options)

        def make_subscribe_options(options):
            return types.SubscribeOptions(**options)

        registration_list = []
        for reg in registrations:

            uri = reg['uri']
            handler = reg['handler']
            options = reg.get('options', {'match' : 'exact'})

            if reg_type == 'subscription':
                options = make_subscribe_options(options)
                registration_list.append(self.register_subscription(uri, handler, options))
            elif reg_type == 'rpc':
                options = make_register_options(options)
                registration_list.append(self.register_rpc(uri, handler, options))

        d_caller = Deferred()

        dlist = DeferredList(registration_list, fireOnOneErrback=True, consumeErrors=True)
        dlist.addCallbacks(registrations_succeeded, registrations_failed, errbackArgs=(d_caller,))
        return d_caller

    def register_subscription(self, uri, handler, options):
        """
        Send a topic subscription request to the router.
        Returns a deferred
        """
        self.log.info('REGISTRATION:{name} Attempting to subscribe to topic {uri}', name=self.plugin_name, uri=uri)
        def suc(res):
            self.log.info('REGISTRATION:Subscribed to topic:{uri}', uri=uri)

        d = self.session.subscribe(handler, uri, options)
        d.addCallback(suc)
        return d

    def register_rpc(self, uri, handler, options):
        """
        Send a RPC registration request to the router.
        Returns a deferred
        """
        self.log.info('REGISTRATION:{name} Attempting to register RPC {uri}', name=self.plugin_name, uri=uri)
        def suc(res):
            self.log.info('REGISTRATION:{name} Registered RPC {uri}', name=self.plugin_name, uri=uri)

        d = self.session.register(handler, uri, options)
        d.addCallback(suc)
        return d
