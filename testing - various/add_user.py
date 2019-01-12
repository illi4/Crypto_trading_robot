import argparse
from sqltools import query_lastrow_id, query        # proper requests to sqlite db

# Parse custom params if there are any
parser = argparse.ArgumentParser()
parser.add_argument('--userid', type=int, help="User id (telegram")
parser.add_argument('--name', type=str, help="User name")
args, unknown = parser.parse_known_args()
user_id = getattr(args, 'userid')
name = getattr(args, 'name')

# Add the user
sql_string = "INSERT INTO user_info(userid, name) VALUES ({}, '{}')".format(user_id, name)
query(sql_string)

sql_string = "INSERT INTO user_params(userid, param_name, param_val) VALUES ({}, '{}', {})".format(user_id, 'margin', 5)
query(sql_string)

print 'Added'
