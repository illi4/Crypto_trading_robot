## Custom libraries 
from loglib import logfile # logging
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import config 
from sqltools import query_lastrow_id, query        # proper requests to sqlite db

# Utilities 
class aux_functions(object):
    def __init__(self):
        self.public = ['strictly_increasing', 'equal_or_increasing', 'strictly_decreasing', 'equal_or_decreasing']
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
                
    def terminate_w_message(self, logger, short_text, errtext):
        logger.lprint([short_text])
        self.send_notification(market, chat, short_text, errtext)
        logger.close_and_exit()
        
    ##################### Check if cancellation was requested through Telegram 

    def check_cancel_flag(self, job_id):
        keep_running = True 
        sql_string = "SELECT abort_flag FROM buys WHERE job_id = '{}'".format(job_id)
        print sql_string ##TEST 
        rows = query(sql_string)
        print rows 
        flag_terminate = rows[0][0] # first result 
        print flag_terminate
        
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
        rows = query(sql_string)

        try: 
            sell_flag = rows[0][0] # first result 
        except: 
            sell_flag = 0
        if (sell_flag == 1): 
            sell_initiate = True
        return sell_initiate