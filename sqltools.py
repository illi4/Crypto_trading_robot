import sqlite3 as lite

def query (sql):
    con = lite.connect('workflow.db', timeout = 10)
    with con:
        cur = con.cursor()
        cur.execute(sql)
        res = cur.fetchall()
    if con:
        con.commit()
        con.close()
    return res

def query_lastrow_id(sql):
    con = lite.connect('workflow.db', timeout = 10)
    with con:
        cur = con.cursor()
        cur.execute(sql)
        res = cur.fetchall()
        last_id = cur.lastrowid
    if con:
        con.commit()
        con.close()
    return last_id, res 
 