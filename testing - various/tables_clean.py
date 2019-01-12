import sqlite3 as lite
import sys

# DATABASE CLEANUP
db = lite.connect('workflow.db')
cur = db.cursor() 

cleanup_jobs = False 

if cleanup_jobs: 
    cur.execute("DROP TABLE IF EXISTS jobs")
    cur.execute("CREATE TABLE jobs(job_id INTEGER PRIMARY KEY, market TEXT, tp FLOAT, sl FLOAT, simulation INT, mooning INT, selling INT, price_curr FLOAT, percent_of FLOAT, abort_flag INT, stop_loss INT, entry_price FLOAT, mode TEXT, tp_p FLOAT, sl_p FLOAT)")
    db.commit()
    print "Cleaned JOBS table" 
    
cleanup_buys = False 

if cleanup_buys: 
    cur.execute("DROP TABLE IF EXISTS buys")
    cur.execute("CREATE TABLE buys(job_id INTEGER PRIMARY KEY, market TEXT, price_fixed INT, price FLOAT, abort_flag INT, source_position FLOAT, mode TEXT)")
    db.commit()
    print "Cleaned BUY table" 
    
cleanup_wf = False 

if cleanup_wf: 
    cur.execute("DROP TABLE IF EXISTS workflow")
    cur.execute("CREATE TABLE workflow(wf_id INTEGER PRIMARY KEY, market TEXT, trade TEXT, currency TEXT, tp FLOAT, sl FLOAT, sell_portion FLOAT, sum_q FLOAT, avg_price FLOAT, run_mode TEXT, price_entry FLOAT)")
    db.commit()
    print "Cleaned WF table" 

cleanup_long = False 
    
if cleanup_long: 
    cur.execute("DROP TABLE IF EXISTS longs")
    cur.execute("CREATE TABLE longs(long_id INTEGER PRIMARY KEY, market TEXT, ep FLOAT, quantity FLOAT)")
    db.commit()
    print "Cleaned longs table" 
    
cleanup_bback = False 
    
if cleanup_bback: 
    cur.execute("DROP TABLE IF EXISTS bback")
    cur.execute("CREATE TABLE bback(id INTEGER PRIMARY KEY, market TEXT, bb_price FLOAT, curr_price FLOAT, trade_price FLOAT, abort_flag INT)")
    db.commit()
    print "Cleaned bback table"    

cleanup_alerts = False 
    
if cleanup_alerts: 
    cur.execute("DROP TABLE IF EXISTS alerts")
    cur.execute("CREATE TABLE alerts(id INTEGER PRIMARY KEY, market TEXT, price FLOAT, direction TEXT, abort_flag INT)")
    db.commit()
    print "Cleaned alerts table"    

cleanup_losses = False 
    
if cleanup_losses: 
    cur.execute("DROP TABLE IF EXISTS losses")
    cur.execute("CREATE TABLE losses(id INTEGER PRIMARY KEY, market TEXT, count INT)")
    db.commit()
    print "Cleaned losses table"    

cleanup_exchange = True 
    
if cleanup_exchange: 
    cur.execute("DROP TABLE IF EXISTS exchange")
    cur.execute("CREATE TABLE exchange(id INTEGER PRIMARY KEY, market TEXT, exchange TEXT)")
    db.commit()
    print "Cleaned losses exchange"    
   
print "Done"
