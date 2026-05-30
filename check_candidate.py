import json
from database.mongodb import db_manager

db_manager.connect()

# Try finding by name (case insensitive)
import re
c = db_manager.candidates.find_one({
    'full_name': re.compile('test candidate 2', re.IGNORECASE)
})

if not c:
    # Try by email
    c = db_manager.candidates.find_one({'email': 'saeedmiradeel@gmail.com'})

if not c:
    print('Candidate not found')
else:
    print(json.dumps({
        'name':        c.get('full_name'),
        'email':       c.get('email'),
        'status':      c.get('status'),
        'final_score': c.get('final_score'),
        'mcq_score':   c.get('mcq_score'),
        'mcq_passed':  c.get('mcq_passed'),
        'mcq_breakdown': c.get('mcq_breakdown'),
        'created_at':  str(c.get('created_at')),
        'job_id':      str(c.get('job_id')),
    }, indent=2))

db_manager.disconnect()
