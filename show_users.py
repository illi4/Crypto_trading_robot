import sqlite3 as lite
import sys

from sqltools import query_lastrow_id, query        # proper requests to sqlite db

request = "SELECT * FROM user_info"
rows = query(request)
for elem in rows: 
    print(elem) 