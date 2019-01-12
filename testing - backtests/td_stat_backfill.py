import pandas as pd
import numpy as np
import libs.sqltools as sqltools
sql = sqltools.sql()

import sqlite3
from datetime import datetime
import time

from sys import exit

# TD analysis library
import libs.tdlib as tdlib
td_info = tdlib.tdlib()

## Backtest import
import backtest
b_test = backtest.backtesting()

#market = 'USD-BTC'
market = 'USDJPY'
exchange = 'oanda'  #'bmex'
firstrun =  False    # (!!!!!!!!!!!!) careful, put as False for the next backfills

period_arr = ['30min', '4h', '1h', '12h', '1d'] # main one

for period in period_arr:

    # Backfill in the cycle, split because of the DST changes
    dates_arr = [
        #[datetime(2011, 10, 3), datetime(2012, 4, 2)],
        #[datetime(2012, 4, 2), datetime(2012, 10, 8)],
        #[datetime(2012, 10, 8), datetime(2013, 4, 8)],
        #[datetime(2013, 4, 8), datetime(2013, 10, 7)],
        #[datetime(2013, 10, 7), datetime(2014, 4, 7)],       #  [datetime(2014, 2, 1), datetime(2014, 4, 7)],
        [datetime(2014, 4, 7), datetime(2014, 10, 6)],
        [datetime(2014, 10, 6), datetime(2015, 4, 6)],
        [datetime(2015, 4, 6), datetime(2015, 10, 5)],
        [datetime(2015, 10, 5), datetime(2016, 4, 4)],
        [datetime(2016, 4, 4), datetime(2016, 10, 3)],
        [datetime(2016, 10, 3), datetime(2017, 4, 3)],
        [datetime(2017, 4, 3), datetime(2017,10, 2)],
        [datetime(2017,10, 2), datetime(2018, 4, 2)],
        [datetime(2018, 4, 2), datetime(2018, 7, 10)]
    ]

    # Updating DB
    for date_interval in dates_arr:
        if firstrun:
            mode =  'replace'
            firstrun = False
        else:
            mode = 'append'

        start_time = date_interval[0]
        end_time = date_interval[1]

        print 'Processing period {}, dates {} - {}'.format(period, start_time, end_time)

        b_test.init_testing(start_time, end_time, exchange, market)  # to enable backtesting

        barsb = td_info.stats(market, exchange, period, 15000000, 15000000, False, b_test = b_test)      # this works fine;   #15000000

        # TEST
        '''
        barsb['time_st'] = barsb.index
        barsb = barsb.drop(barsb[barsb.time_st < start_time].index)
        barsb = barsb.drop(barsb[barsb.time_st > end_time].index)
        print barsb.tail(10)
        exit(0)
        '''
        #TEST

        if period <> '10min':
            bars_ma_30 = td_info.stats_MA_only(market, exchange, period, 30, 150000000, 150000000, False, b_test = b_test)
            bars_ma_20 = td_info.stats_MA_only(market, exchange, period, 20, 150000000, 150000000, False, b_test = b_test)
            bars_ma_10 = td_info.stats_MA_only(market, exchange, period, 10, 150000000, 150000000, False, b_test = b_test)
            bars_ma_30_exp = td_info.stats_MA_only(market, exchange, period, 30, 15000000, 15000000, False, b_test = b_test, ma_calc = 'exponential')
            bars_ma_20_exp = td_info.stats_MA_only(market, exchange, period, 20, 15000000, 15000000, False, b_test = b_test, ma_calc = 'exponential')
            bars_ma_10_exp = td_info.stats_MA_only(market, exchange, period, 10, 15000000, 15000000, False, b_test = b_test, ma_calc = 'exponential')

            barsb['ma_30'] = bars_ma_30
            barsb['ma_20'] = bars_ma_20
            barsb['ma_10'] = bars_ma_10
            barsb['ma_30_exp'] = bars_ma_30_exp
            barsb['ma_20_exp'] = bars_ma_20_exp
            barsb['ma_10_exp'] = bars_ma_10_exp

        #print barsb['ma_30'].tail(25)

        barsb['time_st'] = barsb.index
        barsb['market'] = market
        barsb['period'] = period

        # Dropping excessive (incorrect due to dst) rows
        barsb = barsb.drop(barsb[barsb.time_st < start_time].index)
        barsb = barsb.drop(barsb[barsb.time_st > end_time].index)

        #print barsb.tail(5)

        conn = sqlite3.connect("workflow.db")
        barsb.to_sql("td_stats", conn, if_exists=mode)  # replace or append
        conn.commit()
        conn.close()

exit(0)


#################
#################
# Only updates - TODO
#conn = sqlite3.connect("workflow.db")

sql_string = "SELECT time_stamp FROM td_stats where market = '{}' and period = '{}' " \
    "order by timestamp desc limit 10".format('USD-BTC', '4h')
last_db_timestamps = query(sql_string)  #[0][0]
timestamps_arr = []
for row in last_db_timestamps:
    timestamps_arr.append(row[0])
last_db_timestamp = np.array(timestamps_arr)

print last_db_timestamp


exit(0)

last_row = barsb.values[-1].tolist()
last_index = barsb.index[-1]
last_timestamp = last_row[12]
print last_timestamp, last_index #timestamp

sql_string = "SELECT time_stamp FROM td_stats where market = '{}' and period = '{}' " \
    "order by timestamp desc limit 1".format('USD-BTC', '4h')
last_db_timestamp = query(sql_string)[0][0]
print last_db_timestamp

# Insert new values
if last_db_timestamp <> last_timestamp:
    print 'UPDATING'
    #sql_string = 'INSERT INTO workflow(market, trade, currency, tp, sl, sell_portion, run_mode, exchange, userid)'\
    #        'VALUES (\'{}\', '{}', '{}', {}, {}, {}, '{}', '{}', {})'.format(
    #            robot.market, robot.trade, robot.currency, 0.000000001, 10000000, 0, 'r', 'bmex', robot.user_id)
    #values_str = "({}) ".format(last_row[0], last_row[1], )

#conn.commit()
#conn.close()

#barsb.to_pickle('pkl/USD-BTC_pickle')

#zzz = pd.read_pickle('pkl/USD-BTC_pickle')
#print zzz.tail(20)

#barsb = td_info.stats_rsi_only('USD-BTC', 'bmex', '4h', 150000, 200, False, b_test = b_test)      # this works fine;
#print barsb.tail(20)

#test = td_info.stats_MA_only('USD-BTC', 'bmex', '4h', 20, 150000, 30, False, b_test = b_test, ma_type = 'exponential')
#print test.tail(20)


#barsb = td_info.stats('NEOG18', 'bmex', '1h', 150000, 10, False)      # this works fine;
