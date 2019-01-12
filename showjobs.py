import sqlite3 as lite
import sys

# IN THE BEGINNING 
db = lite.connect('workflow.db')
cur = db.cursor() 

print("TP/SL")
cur.execute("SELECT * FROM jobs")

rows = cur.fetchall()
for row in rows:
    print(row)
    
print("Buys")
cur.execute("SELECT * FROM buys")

rows = cur.fetchall()
for row in rows:
    print(row)
    
print("Workflow")
cur.execute("SELECT * FROM workflow")

rows = cur.fetchall()
for row in rows:
    print(row)
    
print("Longs")
cur.execute("SELECT * FROM longs")

rows = cur.fetchall()
for row in rows:
    print(row)
    
# Checking specific 
'''
market = 'BTC-MCO'
sql_string = "SELECT job_id FROM jobs WHERE market = '{}'".format(market)
cur.execute(sql_string)
rows = cur.fetchall()
for row in rows:
    print row
'''