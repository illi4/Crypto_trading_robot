import sqlite3 as lite
import sys

from sqltools import query_lastrow_id, query        # proper requests to sqlite db

print "\n\n\n\n"

for elem in ['workflow', 'bback', 'buys', 'jobs']: 
    request = "DELETE FROM {}".format(elem)
    print request
    query(request)

print "Done"
