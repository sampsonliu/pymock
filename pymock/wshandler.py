from logging import Handler

class WebsocketHandler(Handler):
    def __init__(self, clients_getter):
        Handler.__init__(self)
        self.clients_getter = clients_getter

    def emit(self, record):
        try:
            msg = self.format(record)
            for client in self.clients_getter():
                client.send_log(msg)
        except Exception:
            self.handleError(record)