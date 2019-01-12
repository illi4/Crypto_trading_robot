# Imports
import os
import csv
from time import sleep, time

# Custom libraries and config
import config
import libs.sqltools as sqltools
import exch_api

from libs.aux_functions import send_chat_message


### Init values for stuff
sql = sqltools.sql()
e_api = exch_api.api(user=config.telegram_chat_id)

# Vars
dir_from = config.dir_from
dir_to = config.dir_to

start_time_dir_copy = start_time = time()
file_prefix = 'price_log/'


### Define filename
def filename_define(file_prefix, market, exch_use):
    market=market.replace('/', '_')
    return '{}{}_{}.csv'.format(file_prefix, market, exch_use.lower())

### Filenames and directories
def file_dirs():
    # Getting file names
    file_dict = {}
    failed_attempts_dict = {}   # failed attempts
    time_failed = {}

    for elem in config.markets_list:

        name_id = '_'.join([elem[0], elem[1].lower()])
        filename = filename_define(file_prefix, elem[0].upper(), elem[1].lower())
        file_dict[name_id] = filename

        failed_attempts_dict[elem[0]] = 0

        # Initial point for prices
        print("Preparing: filenames('{}', '{}', {}); name id {}, file {}".format(elem[1], elem[0], elem[2], name_id, file_dict[name_id] ))

    # Failed timer milestone
    for elem in config.markets_list:
        time_failed[elem[0]] =  time()

    return file_dict, time_failed, failed_attempts_dict


### Check dirs
def check_dir():
    # Creating the price_log folder if required
    directory = os.path.dirname('price_log')
    try:
        os.stat('price_log')
    except:
        os.mkdir('price_log')

######################
def append_line(data, filename):

    with open(filename, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(data)
        print("-- price added in the price log")


### Exchange asssets names generator
def asset_names(exch_abbr):
    list = [(item[0]) for item in config.markets_list if item[1] == exch_abbr.upper()]
    return list

### Map exch full name to abbt
def map_exchange_name(abbr):
    if abbr == 'bitmex':
        return 'bmex'
    elif abbr == 'oanda':
        return 'oanda'

# Update market info in the db (price)
def update_db_price(instrument, price):
    if price is None:
        price = 0

    sql_string = "SELECT id FROM market_info WHERE market = '{}'".format((instrument))
    #print(sql_string)

    rows = sql.query(sql_string)
    if rows != []:
        # Existing - updating
        key_row_id = rows[0][0]
        sql_string = "UPDATE market_info SET price = {}, last_update = {} WHERE id = {}".format(price, time(), key_row_id)
        #print (sql_string)
        sql.query(sql_string)
    else:
        # New - inserting
        sql_string = "INSERT INTO market_info(market, price, last_update) VALUES ('{}', {}, {})".format((instrument), price, time())
        #print(sql_string)
        sql.query(sql_string)

# Check updates
def update_dictionaries(elem, ticker):
    global prices_last_dict, updates_last_dict

    if prices_last_dict[elem] != ticker:
         prices_last_dict[elem] = ticker
         updates_last_dict[elem] = time()

### Add the price line for an element
def add_price(exch_name, elem, price_ticker):

    id = "{}_{}".format(elem.upper(), map_exchange_name(exch_name))
    filename = file_dict[id]

    timestamp = time()
    data = [timestamp, price_ticker]

    append_line(data, filename)

### Run the price grabber
def run(instruments_bitmex, instruments_oanda, e_api):

    # Run for bitmex and oanda
    exch_dict = {
        'bitmex': instruments_bitmex,
        'oanda': instruments_oanda
    }

    while True:

        # Exchanges
        for exch_name, exch_arr in exch_dict.items():
            for elem in exch_arr:

                # Check trading hours
                try:
                    market_open = e_api.is_market_open(exch_name, elem)
                except:
                    notify_text = "Warning: cannot check if the market is open (connection issues)"
                    print(notify_text)
                    send_chat_message(config.telegram_chat_id, notify_text)

                if market_open:
                    # Get the prices
                    try:
                        price_ticker = float(e_api.getticker(exch_name, elem))
                    except:
                        price_ticker = None

                    print("> {}: {}".format(elem, price_ticker))

                    # If not None
                    if price_ticker is not None:
                        update_db_price(elem, price_ticker)
                        print("-- DB updated")
                    else:   # something is wrong
                        notify_text = "Warning: no price value for {}. Not updating the DB.".format(elem)
                        print(notify_text)
                        send_chat_message(config.telegram_chat_id, notify_text)
                else:
                    print("> Market is closed for {}".format(exch_name))
                    price_ticker = None

                ## Logging prices
                if price_ticker is not None:
                    add_price(exch_name, elem, price_ticker)

        # File copies if needed
        price_files_copy()

        # Sleep for all
        sleep(1)


### To copy price files
def price_files_copy():
    global start_time, start_time_dir_copy

    # Copies
    if (start_time - start_time_dir_copy) > 43200:
        start_time_dir_copy = start_time
        os.system('cp -R ' + dir_from + ' ' + dir_to)


### To update elem dictionaries
def dicts_values_init(lists):
    for list in lists:
        for elem in list:
            prices_last_dict[elem] = 0
            updates_last_dict[elem] = time()


##############################
###                   Main                          ###
#############################

if __name__ == "__main__":

    # Price log directory check
    check_dir()

    # Filenames
    file_dict, time_failed, failed_attempts_dict = file_dirs()

    bitmex_list = asset_names('bmex')
    oanda_list = asset_names('oanda')

    # Prices control - to notify if there are issues with prices not being updated
    prices_last_dict = {}
    updates_last_dict = {}
    problematic_assets = set()

    # Update values with initial
    dicts_values_init([bitmex_list, oanda_list])

    # Run processing forever
    run(bitmex_list, oanda_list, e_api)

