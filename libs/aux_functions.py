## Custom libraries

from .loglib import logfile # logging
import smtplib
import traceback

# Not used
#from email.MIMEMultipart import MIMEMultipart
#from email.MIMEText import MIMEText

import config 

import telegram as telegram_python_bot  # for bare wrapper to send files

import libs.sqltools as sqltools
sql = sqltools.sql()

# Telegram messaging
bot = telegram_python_bot.Bot(config.telegram_token)

### Helper functions
# Send chat messages
def send_chat_message(user_to, text):
    try:
        if not config.backtesting_enabled:
            bot.send_message(
                chat_id=user_to,
                text=text,
                timeout=30
            )
    except:
        err_msg = traceback.format_exc()
        print("\n(i) Note: Failed to send telegram message. Reason: \n------{}\n------".format(str(err_msg)))

### Utilities, in a class
class aux_functions(object):
    def __init__(self):
        self.public = ['strictly_increasing', 'equal_or_increasing', 'strictly_decreasing',
                       'equal_or_decreasing', 'send_notification', 'terminate_w_message'
                       ]

        #### Gmail login and pass (if used) 
        self.fromaddr = config.fromaddr   
        self.toaddr = config.toaddr    
        self.email_passw = config.email_passw
        self.comm_method = config.comm_method 
        self.send_messages = True
    
    # Comparison functions 
    def strictly_increasing(self, L):
        return all(x<y for x, y in zip(L, L[1:]))
       
    def equal_or_increasing(self, L):
        return all(x<=y for x, y in zip(L, L[1:]))

    def strictly_decreasing(self, L):
        return all(x>y for x, y in zip(L, L[1:]))
        
    def equal_or_decreasing(self, L):
        # Actually >= for our purposes
        return all(x>=y for x, y in zip(L, L[1:]))

    # Deprecated, delete
    def send_notification(self, market, chat, subj, text):       
        if self.send_messages:
            if self.comm_method == 'mail':
                msg = MIMEMultipart()
                msg['From'] = self.fromaddr
                msg['To'] = self.toaddr
                msg['Subject'] = market + ': ' + subj
                body = text
                msg.attach(MIMEText(body, 'plain'))
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(self.fromaddr, email_passw)
                text = msg.as_string()
                server.sendmail(self.fromaddr, self.toaddr, text)
                server.quit()  
            else: 
                chat.send(text)
                
    def terminate_w_message(self, market, logger, short_text, errtext):
        logger.lprint([short_text])
        self.send_notification(market, chat, short_text, errtext)
        logger.close_and_exit()
        
    ##################### Check if cancellation was requested through Telegram 

    def check_cancel_flag(self, job_id):
        keep_running = True 
        sql_string = "SELECT abort_flag FROM buys WHERE job_id = '{}'".format(job_id)
        print(sql_string) ##TEST 
        rows = sql.query(sql_string)
        print(rows) 
        flag_terminate = rows[0][0] # first result 
        print(flag_terminate)
        
        #try: 
        #    flag_terminate = rows[0][0] # first result 
        #except: 
        #    flag_terminate = 0
        if (flag_terminate == 1): 
            keep_running = False
        return keep_running

        
    # Checking if we need to initiate selling from the main or from the mooning cycle 
    def check_sell_flag(self, market, db, cur, job_id):
        
        sell_initiate = False 
        sql_string = "SELECT selling FROM jobs WHERE market = '{}'".format(market)
        rows = sql.query(sql_string)

        try: 
            sell_flag = rows[0][0] # first result 
        except: 
            sell_flag = 0
        if (sell_flag == 1): 
            sell_initiate = True
        return sell_initiate

    # Just a time check function
    def check_time_elapsed(self, time_elapsed, time_interval):
        if time_elapsed is not None:
            if (time_elapsed > time_interval):
                time_check = True
            else:
                time_check = False
        else:
            time_check = True
        return time_check

    # Time now using b_test
    def timenow(self, b_test):
        return b_test.strftime("%Y-%m-%d %H:%M:%S")

    ## Other helper functions
    # Returning the name of direction
    def direction_name(self, direction):
        if direction == 'green':
            return 'long'
        else:
            return 'short'

    ### Processing sell outcome results and generating messages
    def process_stat(self, status, robot, e_api, sql):

        flag = True   # default flag returned
        message = ''

        if status == 'stop':
            message = 'Finishing up normally'
            flag = False
            sql_string = "UPDATE jobs SET selling = 0 WHERE job_id = {} AND userid = {} AND core_strategy = '{}' ".format(
                robot.job_id, robot.user_id, robot.core_strategy)     # DB update
            sql.query(sql_string)
        elif status == 'err_low':
            message = 'Trade amount was too small and returned error, finishing up'
            #self.send_notification(robot.market, chat, 'Error: Too small trade', 'Too small trade to perform, finishing up')
            e_api.cancel_orders(robot.exchange, robot.market)
            flag = False
        elif status == 'no_idea':
            message = 'Sell calls did not return proper answer, aborting'
            #self.send_notification(robot.market, chat, 'Error: No response from sell calls', 'Sell calls did not return proper answer, aborting')
            e_api.cancel_orders(robot.exchange, robot.market)
            flag = False
        elif status == 'abort_telegram':
            message = 'Aborted as requested via Telegram'
            e_api.cancel_orders(robot.exchange, robot.market)
            flag = False
        else:
            message = 'Finished'
            flag = False

        return flag, message