import time as t

# TD analysis library
import libs.tdlib as tdlib
td_info = tdlib.tdlib()

import libs.sqltools as sqltools
sql = sqltools.sql()

import robo_class  # class to store robot job constants and used variables
import config
import _thread

## Backtest import
import backtest

# Pre: Generate from existing, also need control_bars_upd
list_markets_assets = []
for elem in config.markets_list:
    if elem[0].lower() in config.param_dict.keys():
        list_markets_assets.append(elem)

dict_robots = {}
dict_b_tests = {}


# Func to update DB with the prediction
def update_prediction_db(prediction, prediction_probability, market, robo_instance):
        

        if prediction is not None and prediction_probability is not None:
            sql_string = "SELECT id FROM market_info WHERE market = '{}'".format(market)
            rows = sql.query(sql_string)
            #print(sql_string, rows)

            if rows != []:
                # Existing - updating
                key_row_id = rows[0][0]
                sql_string = "UPDATE market_info SET prediction = '{}', probability = {} WHERE id = {}".format(
                    robo_instance.predicted_name(prediction), prediction_probability, key_row_id
                )
                sql.query(sql_string)
                #print(sql_string)
            else:
                # New - inserting
                sql_string = "INSERT INTO market_info(market, prediction, probability) VALUES ('{}', '{}', {})".format(
                    robo_instance.market, predicted_name(prediction), prediction_probability
                )
                sql.query(sql_string)
                #print(sql_string)

# Func to run the calcs
def run_calc(robo_instance, btest_instance):
    firstrun = True

    while True:
        timer_minute = int(btest_instance.strftime("%M"))

        if (timer_minute in robo_instance.control_bars_minutes) or (firstrun):
            label_to_predict = td_info.get_features_realtime(robo_instance, dict_b_tests[market])
            prediction, prediction_probability = td_info.predict_label(label_to_predict, robo_instance)
            print("Market {}, prediction {}, probability {}".format(robo_instance.market, prediction, prediction_probability))
            update_prediction_db(prediction, prediction_probability, robo_instance.market.upper(), robo_instance)

            firstrun = False

        else:
            print("Market {}, timer_minute {}. Sleeping...".format(robo_instance.market, timer_minute))

        btest_instance.sleep(30)

# Create dictionary of robots
for elem in list_markets_assets:

    exchange_abbr = exchange = elem[1].lower()
    market = elem[0] 

    dict_b_tests[market]=backtest.backtesting()
    dict_b_tests[market].init_now(exchange, market)  # just for the current prices

    dict_robots[market] = robo_class.Scripting(None)
    dict_robots[market].market = market
    dict_robots[market].exchange = exchange
    dict_robots[market].exchange_abbr = exchange_abbr
    dict_robots[market].assign_default_values()
    dict_robots[market].update_thresholds()

# Do updates only when needed and write in the db
for key, robo_instance in dict_robots.items():

    print("Starting thread for", robo_instance.market)
    _thread.start_new_thread( run_calc, (robo_instance, dict_b_tests[robo_instance.market], ) )

# Run forever
while True:
    t.sleep(60)
