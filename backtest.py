################################ Libraries ############################################
#import exceptions
import time as t
from datetime import datetime, timedelta
import config
from collections import deque
from sys import exit

## Backtest class
class backtesting(object):
    def __init__(self):
        self.backtesting, self.exchange_abbr, self.market = False, None, None
        self._curr_time, self._curr_price, self._end_time, self._curr_pricelog_line_no = None, None, None, None
        self.finished = False
        self._price_history_queue = deque()
        # For proper timezone and DST handling 
        self.pytz_timezone = config.pytz_timezone
        self.td_price_base_constant = config.td_price_base_constant
        self.timedelta, self.timedelta_current = config.timedelta, config.timedelta 
        self.timedelta_str = ":".join([str(self.timedelta_current), '00', '00'])

        self.file_prefix = 'price_log/'

    # Init b_test object just for now (current prices)
    def init_now(self, exchange_abbr_in, market_in):
        self.init_testing(datetime.now(), datetime.now(), exchange_abbr_in, market_in, ignore_config=True)

    # Defining filename
    def filename_define(self, market, exch_use):
        market = market.replace('/', '_')
        return '{}{}_{}.csv'.format(self.file_prefix, market, exch_use.lower())

    # Init testing with start and end dates
    def init_testing(self, datetime_in, datetime_until, exchange_abbr_in, market_in, ignore_config=False):

        if not ignore_config:
            if config.backtesting_enabled:
                self.backtesting = True
        else:
            self.backtesting = False

        self._curr_time = t.mktime(datetime_in.timetuple())
        self._end_time = t.mktime(datetime_until.timetuple())

        self.exchange_abbr = exchange_abbr_in
        self.market = market_in

        if self.backtesting:
            #with open('price_log/' + self.market + '_' + self.exchange_abbr.lower() + '.csv') as file:
            filename = self.filename_define(self.market, self.exchange_abbr.lower())
            with open(filename) as file:
                start_line_no = 0
                self._curr_pricelog_line_no = -1
                for line in file:
                    strs = line.split(',')
                    self._curr_pricelog_line_no = self._curr_pricelog_line_no + 1
                    # If starting earlier than available - finish
                    if (float(strs[0]) > self._curr_time) and (self._curr_pricelog_line_no == 0):
                        raise exceptions.IndexError('Backtesting time earlier than available')

                    if not start_line_no and float(strs[0]) >= self._curr_time:
                        start_line_no = self._curr_pricelog_line_no

                    if start_line_no:
                        if float(strs[0]) > self._end_time:
                            #print('History will be stopped at the line with attributes {}'.format(line, self._end_time))
                            break
                        else:
                            pair = (float(strs[0])), float(strs[1])
                            self._price_history_queue.append(pair)

            self._curr_pricelog_line_no = start_line_no
            self._find_current_price()

    def get_market_price(self, exchange_abbr_in, market_in, logger = None):
        #print exchange_abbr_in.lower(), self.exchange_abbr.lower(), market_in.lower() , self.market.lower()
        if exchange_abbr_in.lower() != self.exchange_abbr.lower() or market_in.lower() != self.market.lower():
            raise exceptions.InputError('exchange_abbr_in or market_in is incorrect')
        return self._curr_price

    # Finding the current price
    def _find_current_price(self):
        while len(self._price_history_queue) > 0:
            if self._price_history_queue[0][0] >= self._curr_time:
                self._curr_price = self._price_history_queue[0][1]
                return
            else:
                self._price_history_queue.popleft();
                self._curr_pricelog_line_no = self._curr_pricelog_line_no + 1

        #print ('\nCurr line {}, curr time {}\n'.format(self._curr_pricelog_line_no, self._curr_time))
        print('Price history finished')
        self.finished = True
        exit(0)

    def time(self):        
        if not self.backtesting:
            return t.time()
        else:
            return self._curr_time

    def strftime(self, format):
        return t.strftime(format, datetime.fromtimestamp(self.time()).timetuple())

    def sleep(self, seconds):

        if not self.backtesting:
            t.sleep(seconds)
        else:
            self._curr_time += seconds

            if self._curr_time <= self._end_time:
                self._find_current_price()
            else:
                self.finished = True

    def not_supported(self):
        raise exceptions.Exception('not supported in backtesting')