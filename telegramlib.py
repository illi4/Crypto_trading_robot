import json 
import requests
from time import sleep
from sqltools import query_lastrow_id, query # proper requests to sqlite db
from time import localtime, strftime

# Universal functions for all exchanges 
from exchange_func import getticker, getopenorders, cancel, getorderhistory, getorder, getbalance, selllimit, getorderbook, buylimit, getbalances

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

chat_id = config.telegram_chat_id  # my chat id 

# Telegram monitoring interval  
telegram_check_sec = config.telegram_check_sec

class telegram(object):
    def __init__(self):
        self.public = ['get_offset', 'check_upd', 'send', 'get_response']
        self.offset = self.get_offset()
        
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

    def get_updates(self, offset = None):
        if offset is None: 
            url = URL + "getUpdates"
        else: 
            url = URL + "getUpdates?offset=" + str(offset)
        js = self.get_json_from_url(url)
        return js

    def send(self, text):
        url = URL + "sendMessage?text={}&chat_id={}".format(text, chat_id)
        self.get_url(url)

    def check_updates(self):
        try: 
            filtered_requests = []
            
            # To prevent crashes if there is no connection 
            offset_check = self.get_offset()

            offset_compare = self.offset
            self.offset = offset_check
            
            if offset_check > offset_compare:     
                msg_upd = self.get_updates(offset_check)
                for elem in msg_upd["result"]: 
                    if elem["message"]["chat"]["id"] == chat_id: 
                        filtered_requests.append(elem)

                if filtered_requests != []:                  
                    index = len(filtered_requests) - 1
                    print filtered_requests[0]["message"]["text"].lower()
                    # Does not work when in a function #  if index > 0: 
                    # send_telegram('Only processing the last message')
                    return True, offset_check, filtered_requests[0]["message"]["text"].lower()
                else: 
                    return False, offset_check, ''
                
            else: 
                return False, offset_check, ''
        except: 
            return False, 0, ''
            
    def get_response(self):
        try: 
            filtered_requests = []
            flag_reply = False 
            
            while flag_reply != True: 
                offset_check = self.get_offset()

                offset_compare = self.offset
                self.offset = offset_check
                
                log_msg = 'Telegram - offset_check: {}, offset_compare: {}'.format(offset_check, offset_compare)
                print log_msg
                with open("system_msg/continuous.log", "a") as logfile:
                    log_time_msg = strftime("%Y-%m-%d %H-%M-%S", localtime()) + ' : ' + log_msg + '\n'
                    logfile.write(log_time_msg)
                
                if offset_check > offset_compare:     
                    msg_upd = self.get_updates(offset_check)
                    for elem in msg_upd["result"]: 
                        if elem["message"]["chat"]["id"] == chat_id: 
                            filtered_requests.append(elem)

                    if filtered_requests != []:            
                        flag_reply = True 
                        index = len(filtered_requests) - 1
                        
                        log_msg = filtered_requests[0]["message"]["text"].lower()
                        print log_msg
                        with open("system_msg/continuous.log", "a") as logfile:
                            log_time_msg = strftime("%Y-%m-%d %H-%M-%S", localtime()) + ' : ' + log_msg + '\n'
                            logfile.write(log_time_msg)

                        # Does not work when in a function #  if index > 0: 
                        # send_telegram('Only processing the last message')
                        
                        return filtered_requests[0]["message"]["text"].lower()
                sleep(telegram_check_sec)
        except: 
            return ''
