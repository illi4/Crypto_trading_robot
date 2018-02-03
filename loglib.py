################################ Libraries ############################################
## Standard libraries 

from time import localtime, strftime
import logging
import os

### Logfile class 
class logfile(object):
    def __init__(self, market, type):
        self.public = ['initialise', 'write', 'close']
        self.check_dirs(['logs_buy', 'logs_trade', 'system_msg'])       # check directories 
        
        trade_id = market + ' ' + strftime("%Y-%m-%d %H-%M-%S", localtime())
        if type == 'buy': 
            filename = "logs_buy/" + trade_id + ".log"
        elif type == 'trade': 
            filename = "logs_trade/" + trade_id + ".log"
        else: 
            filename = "system_msg/" + trade_id + ".log"
            
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        # Create a file handler
        self.handler = logging.FileHandler(filename)
        self.handler.setLevel(logging.INFO)
        # Create a logging format
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(message)s')
        self.handler.setFormatter(formatter)
        # Add the handlers to the logger
        self.logger.addHandler(self.handler)
    
    def check_dirs(self, dirlist): 
        # Check if required directories exist and create them if not 
        for dir in dirlist:     
            directory = os.path.dirname(dir)
            try:
                os.stat(dir)
            except:
                os.mkdir(dir) 
    
    def write(self, msg):  
        self.logger.info(msg)
        
    def close_and_exit(self):
        self.logger.removeHandler(self.handler)
        del self.logger, self.handler
        exit(0)

    def close(self):
        self.logger.removeHandler(self.handler)
        del self.logger, self.handler