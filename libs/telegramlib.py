import json 
import requests
import time
from datetime import datetime

#from sqltools import query        # proper requests to sqlite db
from . import sqltools
sql = sqltools.sql()

# Config file 
import config 

# Telegram functions 
TOKEN = config.telegram_token
URL = config.telegram_url

payload = ""
headers = {
    'x-api-key': config.telegram_key,
    'x-api-secret': config.telegram_secret,
    'content-type': "application/json"
    }

# Telegram monitoring interval  
telegram_check_sec = config.telegram_check_sec

class telegram(object):
    def __init__(self, chat_id, start_override = False):
        self.public = ['get_offset', 'check_upd', 'send', 'get_response']
        self.chat_id = chat_id
        self.status = ''
        self.start_override = start_override
        self.last_update_id = None # workaround (repeated messages)

        # Periodic health reports for the admin
        self.report_status = True
        self.hour_system_msg = int(time.strftime("%I")) - 4
        self.status_msg_h = ''
        self.report_to = config.telegram_chat_id

        # Selecting the user name (not just id)
        sql_string = "SELECT name FROM user_info WHERE userid = {}".format(chat_id)
        try:
            rows = sql.query(sql_string)
            self.user_name = rows[0][0]
        except:
            self.user_name = ''

        #if (not config.backtesting_enabled) or (self.start_override):
        #    self.offset = self.get_offset()
        #else:
        #    print "Telegram disabled: backtesting is on"
        
    def get_offset(self):  
        msg_upd = self.get_updates()
        updates = msg_upd["result"]

        last_update = len(msg_upd["result"]) - 1
        offset = msg_upd["result"][last_update]["update_id"]

        return offset
        
    def get_url(self, url):
        try: 
            response = requests.get(url)
            content = response.content.decode("utf8")
            return content
        except: 
            return '' 
            
    def get_json_from_url(self, url):
        content = self.get_url(url)
        js = json.loads(content)
        return js

    # Getting updates and resetting offset periodically
    def get_updates(self, offset = None):
        if offset is None:
            url = URL + "getUpdates"
        else:
            url = URL + "getUpdates?offset=" + str(offset)
        js = self.get_json_from_url(url)
        return js

    def send(self, text, to_overwrite = None):
        if not config.backtesting_enabled or self.start_override:
            try:
                if to_overwrite is None:
                    # Adding a debug
                    #text = ''.join([text, '\n\n--debug: user ', str(self.chat_id), '| offset: ', str(self.offset)])
                    url = URL + "sendMessage?text={}&chat_id={}".format(text, self.chat_id)
                else:
                    # Adding a debug
                    #text = ''.join([text, '\n\n--debug: user ', str(to_overwrite), '| offset: ', str(self.offset)])
                    url = URL + "sendMessage?text={}&chat_id={}".format(text, to_overwrite)
                self.get_url(url)
            except UnicodeDecodeError:
                text = '(i) cannot send the proper status message'
                url = URL + "sendMessage?text={}&chat_id={}".format(text, self.chat_id)
                self.get_url(url)

    def send_gif(self, gifurl):
        if not config.backtesting_enabled or self.start_override:
            url = URL + "sendDocument?document={}&chat_id={}".format(gifurl, self.chat_id)
            self.get_url(url)
    
    def status_report(self): 
        if self.report_status:
            hour_upd = int(time.strftime("%I"))
            status_msg = "(i) hour_upd {}, hour_system_msg {}".format(hour_upd, self.hour_system_msg)  # DEBUG
            if status_msg != self.status_msg_h:
                print(status_msg)
                self.status_msg_h = status_msg

            if abs(hour_upd - int(self.hour_system_msg)) >= 4:  # every 4 hours
                self.hour_system_msg = hour_upd
                filename = 'price_log/BTC_USD_bmex.csv'
                with open(filename, "r") as f1:
                    last_line = f1.readlines()[-1]
                last_line = last_line.split(',') 
                last_line[0] = datetime.fromtimestamp(float(last_line[0]))
                msg = "\n".join(['ℹ Daemon active, last price line:', str(last_line[0]), last_line[1]])
                self.send(msg, self.report_to)