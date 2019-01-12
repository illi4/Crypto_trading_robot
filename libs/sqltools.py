import sqlite3 as lite

# SQL connection / query class
class sql:
    def __init__(self):
        self.dbname = 'workflow.db'
        self.timeout = 30

    # Return a query result
    def query (self, sql):
        con = lite.connect(self.dbname, timeout = self.timeout)
        with con:
            cur = con.cursor()
            cur.execute(sql)
            res = cur.fetchall()
        if con:
            con.commit()
            con.close()
        return res

    # Return a query result and the record id
    def query_lastrow_id(self, sql):
        con = lite.connect(self.dbname, timeout = self.timeout)
        with con:
            cur = con.cursor()
            cur.execute(sql)
            res = cur.fetchall()
            last_id = cur.lastrowid
        if con:
            con.commit()
            con.close()
        return last_id, res

    # Check if a market is supported
    def is_market_supported(self, market):
        sql_string = "SELECT id FROM markets WHERE market = '{}'".format(market)
        rows = self.query(sql_string)
        if rows == []:
            return False
        else:
            return True

    # Checking if we need to stop buyback
    def check_bb_flag(self, robot):

        sql_string = "SELECT abort_flag FROM bback WHERE id = {} AND userid = {}".format(robot.bb_id, robot.user_id)
        rows = self.query(sql_string)

        try:
            bb_flag = rows[0][0] # first result
        except:
            bb_flag = 0
        return bool(bb_flag)

    # Checking cancel flag
    def check_cancel_flag(self, robot, job_id, table):

        keep_running = True
        sql_string = "SELECT abort_flag FROM {} WHERE job_id = '{}' AND userid = {}".format(table, job_id, robot.user_id)
        rows = self.query(sql_string)
        try:
            flag_terminate = rows[0][0] # first result
        except:
            flag_terminate = 0
        if flag_terminate == 1:
            keep_running = False
        return keep_running

    # Checking sell flag
    def check_sell_flag(self, robot):
        sell_initiate = False
        sql_string = "SELECT selling FROM jobs WHERE market = '{}' AND userid = {} " \
                     "AND core_strategy = '{}'".format(robot.market, robot.user_id, robot.core_strategy)
        rows = self.query(sql_string)

        try:
            sell_flag = rows[0][0]  # first result
        except:
            sell_flag = 0
        if sell_flag == 1:
            sell_initiate = True
        return sell_initiate