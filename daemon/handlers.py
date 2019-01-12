import signal

from abc import abstractmethod

from utils import Loggable


class SigInt(Loggable):
    @property
    def signal(self):
        return signal.SIGINT

    def on_start(self, app):
        pass

    def on_signal(self, app):
        self.log.info("Received SIGINT, stopping...")
        self.on_exit()
        app.stop()

    @abstractmethod
    def on_exit(self):
        pass


class SigAlarm(Loggable):
    @property
    def signal(self):
        return signal.SIGALRM

    def on_start(self, app):
        self.schedule()

    def schedule(self):
        signal.alarm(1)

    def on_signal(self, app):
        if app.running:
            self.log.debug("Listener is still running, re-scheduling wake-up")
            self.on_alarm()
            self.schedule()
        else:
            self.log.info("The listener has been stopped, no re-scheduling of wake-up")

    @abstractmethod
    def on_alarm(self):
        pass
