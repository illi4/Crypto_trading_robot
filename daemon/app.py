import signal

from utils import Loggable


class AppRunner(Loggable):
    def __init__(self):
        super(AppRunner, self).__init__()
        self.__running = True
        self.__handlers = []

    @property
    def running(self):
        return self.__running

    def register(self, handler):
        self.__handlers.append(handler)
        return self

    def start(self):
        self.log.info("Starting...")

        signals = []

        for handler in self.__handlers:
            if handler.signal not in signals:
                signals.append(handler.signal)
                signal.signal(handler.signal, self)

            handler.on_start(self)

        self.log.info("Started!")

    def stop(self):
        self.__running = False

    def run(self):
        self.start()
        while self.running:
            self.log.debug("Listening...")
            signal.pause()
        self.log.info("Stopped!")

    def __call__(self, sig, frame):
        found = False
        for handlers in self.__handlers:
            if handlers.signal == sig:
                try:
                    found = True
                    handlers.on_signal(self)
                except () as err:
                    self.log.error("Exception while executing handler!", err)

        if not found:
            self.log.warn("Received unsupported signal!")
