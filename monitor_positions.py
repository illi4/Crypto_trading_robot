import config
import exch_api  # exchanges

from libs.aux_functions import send_chat_message

import libs.sqltools as sqltools
sql = sqltools.sql()

import time, traceback

# List of users to ignore
ignore_users = [386061351]

# Get the array with active markets
markets_arr = [row[0] for row in config.markets_list]

# Get user list
def get_user_list():
    # Empty array
    tmp_dict = {}

    sql_string = "SELECT userid, name FROM user_info"
    rows = sql.query(sql_string)

    if rows != []:
        for row in rows:
            userid = int(row[0])
            name = row[1]

            tmp_dict[userid] = name

    return tmp_dict


# Overall array of tasks
def tasks_update(type = 'jobs'):
    # Empty array
    tasks_arr = []

    if type == 'jobs': # checking jobs

        sql_string = "SELECT * FROM jobs"
        rows = sql.query(sql_string)

        if rows != []:
            for row in rows:
                id = row[0]
                market = row[1]  # market
                userid = row[16]
                entry = row[11]
                exch = row[15]
                strategy = row[18]
                short_flag = row[19]
                last_update = row[20]

                tmp_dict = {'userid': userid, 'strategy': strategy, 'short_flag': short_flag, 'exchange': exch, 'last_update': last_update, 'market': market, 'id':id}
                tasks_arr.append(tmp_dict)

    elif type == 'positions':

        sql_string = "SELECT user, strategy, exchange, key_id FROM keys"
        rows = sql.query(sql_string)

        if rows != []:
            for row in rows:
                userid = row[0]
                strategy = row[1]
                exchange = row[2]
                keyid = row[3]

                tmp_dict = {'userid': userid, 'strategy': strategy,  'exchange': exchange, 'keyid': keyid}
                tasks_arr.append(tmp_dict)

    return tasks_arr

## Confirming we have jobs
def confirm_jobs(position, userid, markets_arr):

    if position['market'] in markets_arr:
        sql_string = "SELECT * FROM jobs WHERE userid = {} and market = '{}' ".format(userid, position['market'])
        rows = sql.query(sql_string)

        if rows != []:
            return True
        else:
            return False

    else:
        return True

# Pre 
warnings_arr = []

####### Cycle checking  #############
while True:
    
    warnings_repeated_arr = []
    current_ts = time.time()

    # List of users
    user_list = get_user_list()

    ## Check tasks -> positions
    tasks = tasks_update(type='jobs')
    for task in tasks:
        print('Checking task for the user {}, strategy {}'.format(task['userid'], task['strategy']))
        position = None
        e_api = exch_api.api(task['userid'], strategy=task['strategy'])
        all_positions = e_api.getpositions(task['exchange'], task['market'], do_retry=False)
        if all_positions != [{}]:
            position = e_api.getpositions(task['exchange'], task['market'], do_retry=False)[0]

        # If job on no positions
        if position is None:
            issue_str = "\nWarning: orphan job {} for user {} ({})".format(task['id'], task['userid'], user_list[int(task['userid'])])
            if issue_str in warnings_arr: 
                warnings_repeated_arr.append(issue_str)
            else: 
                warnings_arr.append(issue_str)

        # If job stopped updating
        if task['last_update'] is not None:
            if (current_ts - task['last_update'])/60 > 5:
                issue_str = "\nWarning: job {} stopped updating for user {} ({})".format(task['id'], task['userid'], user_list[int(task['userid'])])
                if issue_str in warnings_arr: 
                    warnings_repeated_arr.append(issue_str)
                else: 
                    warnings_arr.append(issue_str)

    ## Check positions -> tasks
    tasks = tasks_update(type='positions')

    for task in tasks:
        print('Checking {}:{}, {}'.format(task['userid'], task['keyid'], task['strategy']))

        if task['userid'] not in ignore_users:   # not for everyone
            e_api = exch_api.api(task['userid'], strategy=task['strategy'])
            all_positions = e_api.getpositions(task['exchange'], do_retry=False)

            if all_positions != [{}]:
                positions_each = e_api.getpositions(task['exchange'], do_retry=False)

                if positions_each is not None:
                    for position in positions_each:
                        check_ok = confirm_jobs(position, task['userid'], markets_arr)
                        if not check_ok:
                            issue_str = "\nWarning: no jobs for open position on {} user {} ({}). Position: {}".format(
                                position['market'], task['userid'], user_list[int(task['userid'])], position)
                            if issue_str in warnings_arr:
                                warnings_repeated_arr.append(issue_str)
                            else:
                                warnings_arr.append(issue_str)

                else:
                    issue_str = "\nWarning: key {} is disabled or inactive for the user {} ({}) | {}".format(
                        task['keyid'], task['userid'], user_list[int(task['userid'])], task['strategy'])
                    if issue_str in warnings_arr:
                        warnings_repeated_arr.append(issue_str)
                    else:
                        warnings_arr.append(issue_str)

    # Processing
    if warnings_repeated_arr != []:
        str_send = 'Issues / warnings\n\n'
        for elem in warnings_repeated_arr:
            str_send = '{}{}\n'.format(str_send, elem)
        send_chat_message(config.telegram_chat_id, str_send)

    print("Sleeping...")
    time.sleep(1800)