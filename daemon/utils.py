import logging

class Loggable(object):
    def __init__(self):
        self.__log = logging.getLogger(self.__class__.__name__)

    @property
    def log(self):
        return self.__log