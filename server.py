#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Hi! I sync Habitica ToDos with Google Reminders.
# Google Reminders are currently accessible through
# the calendar API, but they are NOT officially
# supported. As such, the Reminder interactions are
# subject to change, and could break at any time.
# Use with caution.

import os
import sys
import requests
from flask import Flask, request, render_template, jsonify
import habitica #probably unnecessary
from pprint import pformat, pprint
import subprocess
import random
import string
from ast import literal_eval
from datetime import datetime, timedelta
from functools import wraps
import json
from copy import deepcopy as dc
from windmark import ReminderApi
app = Flask(__name__, static_folder='public', template_folder='templates')

headers={}
#secret constants
if 'HABITICA_USER' in os.environ and 'HABITICA_API_KEY' in os.environ:
  HABITICA_USER=os.environ.get('HABITICA_USER')
  HABITICA_API_KEY=os.environ.get('HABITICA_API_KEY')
#GLITCH_APP_KEY=os.environ.get('GLITCH_APP_KEY') #unused currently
#habitica api requests must be prefixed with this
  headers = {
    'x-api-user': HABITICA_USER,
    'x-api-key': HABITICA_API_KEY
  }
my_url = None
if 'MY_URL' in os.environ:
  my_url = os.environ.get('MY_URL')
TIMEOUT = 5 #seconds
db = '.data/db.txt'
user='.data/user.txt'
DEBUG=True #prints things to console when enabled
userdata={} #will store session details
calv='WRP / /WebCalendar/calendar_190319.03_p1'
gapi = ReminderApi()
protobuf_headers=dc(gapi.headers)
protobuf_headers['content-type'] = 'application/json+protobuf'
up_url = 'https://reminders-pa.clients6.google.com/v1internalOP/reminders/update'
get_url = 'https://reminders-pa.clients6.google.com/v1internalOP/reminders/get'
#NOTE: SERVER APPEARS TO BE IN TZ 00:00
#HABITICA IS IN TZ 00:00
#GOOGLE IS IN LOCAL TZ (est for me)
TZ_OFFSET=0 #SECONDS, I dare you to try otherwise

#list of json objects to install on habitica.
#must be sent via the api, since their web
#interface can be somewhat...special.
#These should be used as the request body.
hooks = []
if my_url:
  hooks = [ {
      "enabled": True,
      "url": my_url + "task_added",
      "label": "Task Created",
      "type": "taskActivity",
      "options": {
        "created": True,
        "updated": False,
        "deleted": False,
        "scored": False
      }
    },{
      "enabled": True,
      "url": my_url + "task_updated",
      "label": "Task Updated",
      "type": "taskActivity",
      "options": {
        "created": False,
        "updated": True,
        "deleted": False,
        "scored": False
      }
    },{
      "enabled": True,
      "url": my_url + "task_deleted",
      "label": "Task Deleted",
      "type": "taskActivity",
      "options": {
        "created": False,
        "updated": False,
        "deleted": True,
        "scored": False
      }
    },{
      "enabled": True,
      "url": my_url + "task_done",
      "label": "Task Done",
      "type": "taskActivity",
      "options": {
        "created": False,
        "updated": False,
        "deleted": False,
        "scored": True
      }
    }
  ]

num_enabled_hooks = 0
for hook in hooks:
  if hook['enabled'] == True:
    num_enabled_hooks += 1
'''
Other hook types:
{
  "enabled": False,
  "url": my_url + "group_chat_received",
  "label": "Group Chat Received",
  "type": "groupChatReceived",
  "options": {
    "groupId": "required-uuid-of-group"
  }
}
{
  "enabled": False,
  "url": my_url + "user_activity",
  "label": "User Activity",
  "type": "userActivity",
  "options": {
    "petHatched": False, 
    "mountRaised": False, 
    "leveledUp": False
  }
}
'''
#dict mapping habitica api names to urls
#this is not an exhaustive list of the api paths
#for more, see https://habitica.com/apidoc/
#some urls need to be built dynamically based on some
#given parameters.
habitica = {
  'create_task':{
    'url':'https://habitica.com/api/v3/tasks/user',
    'params':[],
    'method':'POST'
  },
  'cron':{
    'url':'https://habitica.com/api/v3/cron',
    'params':[],
    'method':'POST'
  },
  'delete_task':{
    'url':'https://habitica.com/api/v3/tasks/taskId',
    'params':['taskId'],
    'method':'DELETE'
  },
  'get_inbox':{
    'url':'https://habitica.com/api/v3/inbox/messages',
    'params':[],
    'method':'GET'
  },
  'get_member_profile':{
    'url':'https://habitica.com/api/v3/members/memberId',
    'params':['memberId'],
    'method':'GET'
  },
  'get_task':{
    'url':'https://habitica.com/api/v3/tasks/taskId',
    'params':['taskId'],
    'method':'GET'
  },
  'get_tasks':{
    'url':'https://habitica.com/api/v3/tasks/user',
    'params':[],
    'method':'GET'
  },
  'get_user_profile':{
    'url':'https://habitica.com/api/v3/user',
    'params':[],
    'method':'GET'
  },
  'verify_api':{
    'url':'https://habitica.com/api/v3/status',
    'params':[],
    'method':'GET'
  },
  'score_task':{
    'url':'https://habitica.com/api/v3/tasks/taskId/score/direction',
    'params':['taskId','direction'],
    'method':'POST'
  },
  'update_task':{
    'url':'https://habitica.com/api/v3/tasks/taskId',
    'params':['taskId'],
    'method':'PUT'
  },
  'feed_pet':{
    'url':'https://habitica.com/api/v3/user/feed/pet/food',
    'params':['pet','food'],
    'method':'POST'
  },
  'login':{
    'url':'https://habitica.com/api/v3/user/auth/local/login',
    'params':[],
    'method':'POST'
  },
  'revive':{
    'url':'https://habitica.com/api/v3/user/revive',
    'params':[],
    'method':'POST'
  },
  'create_hook':{
    'url':'https://habitica.com/api/v3/user/webhook',
    'params':[],
    'method':'POST'
  },
  'delete_hook':{
    'url':'https://habitica.com/api/v3/user/webhook/id',
    'params':['id'],
    'method':'DELETE'
  },
  'edit_hook':{
    'url':'https://habitica.com/api/v3/user/webhook/id',
    'params':['id'],
    'method':'PUT'
  }
}
##############################################################
#          DATABASE INTERACTIONS
#db is just a file right now. It keeps track
#of existing todos/reminders. Each line is a
#map from taskId (habitica) to task name (google).
#e.g. {'hid':'xxxxx', 'gid':'xxxxx', 'name':'xxxxx'}

#can add any python object, e.g. dict or tuple
def add_db_line(line, db=db):
  f = open(db,'a+') #open and create new if needed
  f.write(str(line) + '\n') #append line
  f.close()
  log("add_db_line: " + str(line)[:20] + '...')  
  return True

def erase_db(db=db):
  subprocess.call('rm -f '+db, shell=True)
  log("erase_db")  
  return True

#remove a db line based on the whole line,
#Or UNIQUE text included in that line.
#if includes isn't unique, it will remove the
#first item with matching text.
#this goes through the shell so don't use
#weird characters like quotes in includes.
#case sensitive.
#THIS IS WILDLY INEFFICIENT, WILL NOT SCALE
def rm_db_line(includes, db=db):
  recs = get_db_lines(db)
  erase_db(db)
  new = []
  for rec in recs:
    if str(includes) in str(rec):
      continue
    add_db_line(rec, db) 
  log("rm_db_line")  
  return True

#get a db line based on UNIQUE text, such as
#an id. If multiple results, only returns one.
#case sensitive.
def get_db_line(includes, db=db):
  recs = get_db_lines(db)
  for rec in recs:
    if str(includes) in str(rec):
      log("get_db_line: " + str(rec)[:20] + '...')
      return rec
  log("get_db_line failed: no matching text.")
  return False
  
#returns list of objects in db
def get_db_lines(db=db):
  f = open(db, 'r')
  if not f.mode == 'r': return []
  contents = f.read()
  f.close()
  content_l = list(contents.split('\n'))
  if content_l == [] or content_l[0] == '': return []
  #convert lines to dicts
  #{'taskId':'<id>', 'name':'<name>'}\n
  final = []
  for rec in content_l[:-1]:
    try: 
      new = eval(str(rec))
      final.append(new)
    except: pass
  return final #need deepcopy???

#loads user data from disk into memory
def load_user_data():
  exists = os.path.isfile(user)
  if not exists: return False
  global userdata
  lines = get_db_lines(db=user)
  userdata={}
  for line in lines:
    userdata[line.keys()[0]] = line[line.keys()[0]]
  if load_timezone() and load_headers():
    return True
  return False

def load_headers():
  if 'HABITICA_USER' in os.environ and 'HABITICA_API_KEY' in os.environ:
    HABITICA_USER=os.environ.get('HABITICA_USER')
    HABITICA_API_KEY=os.environ.get('HABITICA_API_KEY')
    global headers
    global userdata
    headers = {
      'x-api-user': HABITICA_USER,
      'x-api-key': HABITICA_API_KEY
    }
    userdata['headers']=headers
    return headers
  return False

def get_env_var(name):
  if not name or name == '': return False
  exists = os.path.isfile('.env')
  if not exists: return False
  #get file contents
  f = open('.env', 'r')
  if not f.mode == 'r': return False
  contents = f.read()
  f.close()
  content_l = list(contents.split('\n'))
  if content_l == [] or content_l[0] == '': return False
  #find variable
  for line in content_l:
    line = line.strip()
    if line[:1] == '#': continue
    if '=' not in str(line): continue
    check = line.split('=')[0]
    if check == name:
      return line.split('=')[1]
  return False

def get_env_file_lines():
  f = open('.env', 'r')
  if not f.mode == 'r': return []
  contents = f.read()
  f.close()
  return list(contents.split('\n'))

#use with EXTREME CAUTION
def erase_env():
  subprocess.call('rm -f .env', shell=True)
  log("erase_env")  
  return True

def rm_env_var(name, ref=True):
  if not get_env_var(name): 
    log('Could not remove env variable ' + str(name) + ' because it does not exist.')
    return False
  lines = get_env_file_lines()
  erase_env()
  new = []
  for line in lines:
    if str(name) in str(line):
      continue
    add_env_line(line, False) 
  if ref: refresh()
  log("rm_env_var: " + str(name))  
  return True

def add_env_line(line, ref=True):
  if not line or line == '': return False
  f = open('.env','a+') #open and create new if needed
  f.write(str(line) + '\n') #append line
  f.close()
  log("add_env_line: " + str(line)[:20] + '...')
  if ref: refresh() #unreliable
  return True

def set_env_var(name, val, ref=True):
  if not val or val == '': return False
  #remove existing value if it exists
  rm_env_var(name, ref)
  #add new value
  line = name + '=' + val
  add_env_line(line, ref)
  return True

#          DATABASE INTERACTIONS
##############################################################
#          UTILITIES

def gen_item_id():
  return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(10))

def interpret_tz(tz_str):
  return timedelta(hours=int(tz_str[:3]), minutes=int(tz_str[:1]+tz_str[4:6])).total_seconds()

#tz must already be present in userdata
#need to add an hour to this value because who tf knows...
#probably compensates for the glitch server system time.
def load_timezone():
  global TZ_OFFSET
  if 'timezone_offset' in userdata.keys():
    TZ_OFFSET = interpret_tz(userdata['timezone_offset']) + 3600
    return TZ_OFFSET
  return False

#takes google json reminder dueDate obj,
#returns google protobuf dueDate obj
def proto_dt_from_json(j):
  p = {
    '1': j['year'],
    '2': j['month'],
    '3': j['day']}
  if 'time' in j: 
    p['4'] = {
      '1': j['time']['hour'],
      '2': j['time']['minute'],
      '3': j['time']['second']
    }
  return p

def proto_dt_from_dt(d):
  return {
    '1': d.year,
    '2': d.month,
    '3': d.day,
    '4': {
      '1': d.hour,
      '2': d.minute,
      '3': d.second}
    }

#return dt
#takes GOOGLE reminder dueDate obj
#google reminders are in local dt
#this can return an object in GMT or local
def dt_from_json(d, gmt=False):
  dt = datetime(year=d['year'], month=d['month'], day=d['day'], 
    hour=d['time']['hour'], minute=d['time']['minute'], second=d['time']['second'])
  if gmt: return dt - timedelta(seconds=TZ_OFFSET) 
  return dt

def login_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if headers == {}:
      log('Call skipped; no headers present.')
      return '510'
    return f(*args, **kwargs)
  return decorated_function

#sends bash command to refresh the project
#seems unstable...may not work as expected
#does not recompile python.
def refresh():
  cmd = 'refresh'
  subprocess.call(cmd, shell=True)
  return True

#TODO: separate log files, autodelete.
#Yeah yeah, I know... TODO: care
def log(msg='', r=None):
  if r != None:
    msg += ('\n' + pformat(eval(json.dumps(r.json()).replace('false', 'False').replace('true', 'True')))).replace('"', "'")
  dt = str(datetime.now()+timedelta(seconds=TZ_OFFSET))
  cmd = '''mkdir ~/logs 2> /dev/null
    echo "''' + str(dt) + ': ' + str(msg) + '" >> ~/logs/log_' + datetime.now().strftime('%Y%m%d') + '.txt'
  try: subprocess.call(cmd, shell=True)
  except: log("unable to write log!!!")
  if DEBUG: print msg
  cmd = "find ~/logs -name 'log*txt' -mmin +7200 -exec rm -f {} \;"
  subprocess.call(cmd, shell=True)
  return True

def create_data_dir():
  cmd = "mkdir ~/.data 2> /dev/null"
  subprocess.call(cmd, shell=True)
  return True

def get_dt_from_task(task):
  task_reminder_times = []
  for t_rem in task['reminders']:
    task_reminder_times.append(datetime.strptime(t_rem['time'], '%Y-%m-%dT%H:%M:%S.%fZ'))
  task_reminder_times.sort()
  stime=None
  for time in task_reminder_times:
    if time > datetime.now():
      stime=time+timedelta(seconds=TZ_OFFSET)
      break
  #if reminder not specified, make it an hour from now.
  if not stime: #THIS IS WORKING
    stime=datetime.now()+timedelta(seconds=TZ_OFFSET)+timedelta(hours=1)
  return stime  

#call when accounts are first linked. adds all 
#tasks from each account to both.
#db: {'serverAssignedId': '1629537192528889588', 'taskId': 'c91e11e7-c7d8-4d81-8765-b54753524a1f'}
def total_sync():
  log('TOTAL SYNC INITIATED.')
  num_new_todos = 0
  num_new_reminders = 0
  erase_db()
  #ADD REMINDERS TO HABITICA AS TODOS
  listresponse = gapi.list()
  grems=[]
  if 'task' in listresponse: grems = listresponse['task']
  for grem in grems:
    #if it doesn't exist in habitica, create it
    #we need the habitica id either way
    htodo = get_todo(text=grem['title'])
    id = None
    #if it doesn't exist, make it
    if not htodo:
      due = datetime.now()+timedelta(hours=1) #works
      if 'dueDate' in grem and dt_from_json(grem['dueDate'], gmt=True) > datetime.now():
        due = dt_from_json(grem['dueDate'], gmt=True)
      r = create_todo(grem['title'], [due])
      id = r.json()['data']['id']
      num_new_todos += 1
    else:
      id = htodo['id']
    #either way, add to db
    add_db_line({'serverAssignedId':grem['taskId']['serverAssignedId'], 'taskId': id})
  #ADD TODOS TO GOOGLE AS REMINDERS
  #for these, only add to db if didn't exist in google.
  r = habitica_req('get_tasks')
  tasks = r.json()['data']
  for task in tasks:
    if task['type'] != 'todo': continue
    grem = get_reminder_by_text(task['text'])
    if grem: continue
    #not in google yet, create reminder.
    #get closest future task reminder
    stime = get_dt_from_task(task)
    sid = create_reminder(task['text'], stime)
    num_new_reminders += 1
    #add to db
    add_db_line({'serverAssignedId':sid, 'taskId': task['id']})
  log('TOTAL SYNC COMPLETE.')
  log('New ToDos:     ' + str(num_new_todos))
  log('New Reminders: ' + str(num_new_reminders))
  return True

#          UTILITIES
##############################################################
#          HABITICA INTERACTIONS

#takes api name as string, and a dict of necessary 
#url components (e.g. 'taskId':'456789'). Returns url string.
def build_url(name, params={}):
  if not name in habitica: raise
  url = habitica[name]['url'] #still has keynames, not values
  if len(habitica[name]['params']) <= 0: return url
  for k in params.keys():
    if not k in habitica[name]['params']: raise
    url = url.replace(k, params[k])
  return url

def habitica_req(name, params={}, data={}, test=None):
  if test: final_headers=test
  else: final_headers=headers
  url = build_url(name, params)
  r = None
  if habitica[name]['method'] == 'POST':
    r = requests.post(url, headers=final_headers, json=data, timeout=TIMEOUT)
  elif habitica[name]['method'] == 'DELETE':
    r = requests.delete(url, headers=final_headers, json=data, timeout=TIMEOUT)
  elif habitica[name]['method'] == 'GET':
    r = requests.get(url, headers=final_headers, timeout=TIMEOUT)
  elif habitica[name]['method'] == 'PUT':
    r = requests.put(url, headers=final_headers, json=data, timeout=TIMEOUT)
  if r == None: raise
  return r

#due should be a dt object already in GMT
def update_todo(taskId=None, oldtext=None, newtext=None, due=None):
  if not newtext and not due: raise
  if not taskId and not oldtext: raise
  if oldtext: taskId = get_todo(text=oldtext)
  if not taskId: return False
  taskId = taskId['id']
  params = {'taskId':taskId}
  body= {}
  if newtext: body['text']=newtext
  if due: body['reminders']=[{
    'startDate': due.isoformat()[:-3]+'Z',
    'time': due.isoformat()[:-3]+'Z'
  }]
  r = habitica_req('update_task', params, body)
  log('update_todo: ', r)
  return r

def get_todo(taskId=None, text=None):
  if not taskId and not text: raise
  if text: #need to find the task by name
    r = habitica_req('get_tasks')
    tasks = r.json()['data']
    for task in tasks:
      if 'text' in task and task['text'] == text:
        taskId = task['id']
    if not taskId:
      log('get_todo failed: no matching text.') 
      return False
  params = {'taskId':taskId}
  r = habitica_req('get_task', params)
  if r.json()['success'] == False:
    log('get_todo failed: no matching id.', r)
    return False
  log('get_todo: ', r)
  return r.json()['data']

#marks the given habitica todo as complete.
#no request body needed for this one
def complete_todo(taskId):
  params = {
    'taskId': taskId,
    'direction':'up'
  }
  r = habitica_req('score_task', params)
  log("complete_todo: ", r)  
  return r

#creates the given habitica todo.
#reminders will be dt list if present
#no params here
#      "reminders": [
#        {
#          "time": "2017-01-13T16:21:00.074Z",
#          "startDate": "2017-01-13T16:20:00.074Z",
#        }        
def create_todo(name, reminders=[], due=None, itemId=''):
  #if not itemId: itemId = gen_item_id()
  body = {
    'text': name,
    'type': 'todo',
    'notes': itemId,
    'priority': 1.5
  }
  if due: body['date'] = due #due date
  if reminders != []:
    body['reminders'] = []
    for dt in reminders:
      date = dt.isoformat()[:-3]+'Z'
      time = dt.isoformat()[:-3]+'Z'
      reminder = {
        'startDate': date,
        'time': time }
      body['reminders'].append(reminder)
  r = habitica_req(name='create_task', data=body)
  #log('create_todo response: ', r)
  log('create_todo: ' + str(r.status_code))
  return r

def delete_todo(taskId=None, itemId=None):
  r = habitica_req(name='delete_task', params={'taskId':taskId})
  log('delete_todo: ' + str(r.status_code))
  return r

def add_webhooks():
  for hook in hooks:
    add_webhook(hook)
  log('add_webhooks')
  return True

def add_webhook(hook):
  r = requests.post(build_url('create_hook'), json=hook, headers=headers, timeout=TIMEOUT)
  log("add_webhook: ", r)
  return r

#returns list of all webhooks, not a request object
def get_all_webhooks():
  #get user profile
  r = requests.get(build_url('get_user_profile'), headers=headers, timeout=TIMEOUT)
  all = json.loads(r.text)['data']['webhooks']
  log("get_all_webhooks: " + pformat(all))
  return all

def delete_webhook(id):
  r = habitica_req(name='delete_hook', params={'id':id})
  log("delete_webhook: ", r)
  return r
  
#USE WITH EXTREME CAUTION
def delete_all_webhooks(existing_hooks=None):
  if not existing_hooks: existing_hooks = get_all_webhooks()
  rlist = []
  for h in existing_hooks:
    hid = h['id']
    rlist.append(delete_webhook(hid))
  log("delete_all_webhooks")
  return rlist

def reinit_hooks():
  delete_all_webhooks()
  add_webhooks()
  log("reinit_hooks")
  return True

def verify_habitica_credentials(id=None, pwd=None):
  if not id or not pwd: return False
  test_headers = {
      'x-api-user': id,
      'x-api-key': pwd
  }
  r = habitica_req(name='get_user_profile', test=test_headers)
  log("credential attempt: " + str(r.status_code))
  if str(r.status_code)[:1] != '2':
    return False
  return True

#          HABITICA INTERACTIONS
##############################################################
#          GOOGLE INTERACTIONS

#currently implemented on the client side
def authenticate_google():
  pass

#marks the given google reminder as complete.
def complete_reminder(cid=None, sid=None, text=None):
  if not cid and not sid and not text: raise
  if text:
    rem = get_reminder_by_text(text)
    if not rem: 
      log('complete_reminder failed: no matching text.')
      return False
    sid = rem['taskId']['serverAssignedId']
  if cid: 
    body={'1': {'4': calv},
        '2': {'2': cid},
        '4': {'1': {'2': cid},
              '8': 1},
        '7': {'1': [1, 10, 3]} }
  elif sid:
    body={'1': {'4': calv},
        '2': {'1': sid},
        '4': {'1': {'1': sid},
              '8': 1},
        '7': {'1': [1, 10, 3]} }
  r = requests.post(up_url, headers=protobuf_headers, json=body)
  log('complete_reminder: ', r)
  return r

#creates the given google reminder.
#dt should already be in local tz.
def create_reminder(text, dt):  
  new = gapi.create(text, dt.strftime('%Y-%m-%d %H:%M'))
  log('create_reminder: ' + pformat(new))
  return new

#takes serverAssignedId
#search by text can only find incomplete reminders
def delete_reminder(text='', sid=None):
  log("delete_reminder")
  if sid: 
    gapi.delete(sid)
    return True
  r = get_reminder_by_text(text)
  if not r:
    log('delete_reminder failed: no matching reminder.')
    return False
  gapi.delete(r['taskId']['serverAssignedId'])
  return True

#returns json object
#search by text can only find incomplete reminders
def get_reminder_by_text(t):
  og = gapi.list()
  if not 'task' in og: return None
  rlist = gapi.list()['task']
  rem=None
  for r in rlist:
    if str(r['title']) == str(t):
      rem = r
  if not rem:
    log('get_reminder_by_text failed: no matching text.')
  return rem

#returns json or protobuf object based on parameters
def get_reminder_by_id(cid=None, sid=None, proto=False):
  if not cid and not sid: raise
  if proto:
    if sid: 
      body={'1': {'4': calv},
            '2': [{'1': sid}]}
    else:
      body={'1': {'4': calv},
            '2': [{'2': cid}]}
    r = requests.post(get_url, headers=protobuf_headers, json=body)
    log('get_reminder_by_id: ' + str(r.status_code))
    return r.json()['1'][0]
  else:
    rlist = gapi.list()['task']
    rem=None
    for r in rlist:
      if cid and str(r['taskId']['clientAssignedId']) == str(cid):
        rem = r
      if sid and str(r['taskId']['serverAssignedId']) == str(sid):
        rem = r
    log('get_reminder_by_id: ' + str(rem))
    return rem

#search by text can only find incomplete reminders
#due should be dt object in local tz
def update_reminder(newtext='', cid=None, sid=None, oldtext=None, due=None):
  if not oldtext and not cid and not sid: raise
  #due will be assigned proto dt obj if applicable
  if due: due = proto_dt_from_dt(due)
  if oldtext:
    rem = get_reminder_by_text(oldtext)
    if not rem:
      log('update_reminder failed: no matching text.')
      return False
    cid = rem['taskId']['clientAssignedId']
    if not due and 'dueDate' in rem: 
      due = proto_dt_from_json(rem['dueDate'])
  elif cid:
    rem = get_reminder_by_id(cid=cid, proto=True)
    if not rem:
      log('update_reminder failed: no matching cid.')
      return False
    if not due and '5' in rem: due = rem['5']
  elif sid:
    rem = get_reminder_by_id(sid=sid, proto=True)
    if not rem:
      log('update_reminder failed: no matching sid.')
      return False
    cid = rem['1']['2']
    if not due and '5' in rem: due = rem['5']
  body={'1': {'4': calv},
        '2': {'2': cid},
        '4': {'1': {'2': cid},
              '3': newtext,
              '8':0 },
        '7': {'1': [0, 3]}
       }
  if due: body['4']['5'] = due
  r = requests.post(up_url, headers=protobuf_headers, json=body)
  log('update_reminder: ' + str(r.status_code), r)
  return r.status_code
  
#          GOOGLE INTERACTIONS
##############################################################
#          FLASK ROUTES

#Google Scripts can call this regularly
#to 'manually' sync tasks without webhooks.
#could also be run as cronjob or subprocess.
@app.route('/total_sync', methods=['GET', 'POST'])
@login_required
def run_total_sync():
  params = request.form.to_dict()
  #FIRST LOGIN!!!
  if not get_env_var('HABITICA_USER'):
    set_env_var('HABITICA_USER', params['huid'])
    set_env_var('HABITICA_API_KEY', params['htoken'])
    init_hooks()
    #check habitica credentials
    test_headers = {
      'x-api-user': params['huid'],
      'x-api-key': params['htoken']
    }
    r = habitica_req(name='get_user_profile', test=test_headers)
    log("credential attempt: " + str(r.status_code))
    if str(r.status_code)[:1] != '2':
      return '500'
    #set habitica creds
    global headers
    headers = dc(test_headers)
  else: load_headers() 
  total_sync()
  return '200'



#Google Scripts can call this regularly
#to ensure that habitica has the correct
#webhooks installed.
#Could also be run as cronjob, or on
#first login.
@app.route('/init_hooks', methods=['GET', 'POST'])
@login_required
def init_hooks():
  installed = get_all_webhooks()
  #if num webhooks != len(hooks):reinit
  if len(installed) != len(hooks):
    reinit_hooks()
  #if not correct num enabled: reinit
  enabled = 0
  for h in installed:
    if h['enabled'] == True:
      enabled += 1    
  if enabled != num_enabled_hooks:
    reinit_hooks()
  log("init_hooks")
  return '200' #can't be bool because reasons

#habitica uses webhooks to call this
#when a task is added.
@app.route('/task_added', methods=['GET', 'POST'])
@login_required
def task_added():
  task = request.json['task']
  #need to check for todo type first
  if str(task['type']) != 'todo': return '201'  
  #if it's for a challenge, ignore it.
  if task['challenge'] != {}: return '202'
  #make sure the reminder doesn't already exist.
  #we don't want an endless loop of task/reminder creation.
  reminder = get_reminder_by_text(task['text'])
  if reminder: return '203'
  db_entry = {'taskId':task['id']}
  #add reminder
  #dt e.g. "2017-01-13T16:21:00.074Z"
  stime = get_dt_from_task(task)
  sid = create_reminder(task['text'], stime)
  #record db entry
  db_entry = {
    'taskId':task['id'].encode('utf8'),
    'serverAssignedId':sid.encode('utf8')
  }
  add_db_line(db_entry)
  log('task_added: '+pformat(request.json))
  return '200'

#habitica uses webhooks to call this 
#when a task is completed.
@app.route('/task_done', methods=['GET', 'POST'])
@login_required
def task_done():
  log("task_done... ")
  task = request.json['task']
  #need to check for todo type first
  if str(task['type']) != 'todo': 
    log('201')
    return '201'  
  #if it's for a challenge, ignore it.
  if task['challenge'] != {}: 
    log('202')
    return '202'
  #if there's an incomplete reminder, complete it
  resp = complete_reminder(text=task['text'])
  #except Exception as e:log("Unexpected error:"+ str(sys.exc_info()[0]) + "" + str(e))
  rm_db_line(task['id'])
  log('200: ' + pformat(request.json))
  return '200'

#habitica uses webhooks to call this 
#when a task is updated.
@app.route('/task_updated', methods=['GET', 'POST'])
@login_required
def task_updated():
  task = request.json['task']
  #need to check for todo type first
  if str(task['type']) != 'todo': return '201'  
  #if it's for a challenge, ignore it.
  if task['challenge'] != {}: return '202'
  newtext = task['text']
  #dt e.g. "2017-01-13T16:21:00.074Z"
  #get closest future reminder
  newtime=get_dt_from_task(task)
  #figure out which reminder is counterpart (from db)
  db_rec = get_db_line(task['id'])
  if not db_rec: return '520'
  sid = db_rec['serverAssignedId']
  update_reminder(newtext=newtext, sid=sid, due=newtime)
  log("task_updated: "+pformat(request.json))
  return '200'

#habitica uses webhooks to call this 
#when a task is deleted.
@app.route('/task_deleted', methods=['GET', 'POST'])
@login_required
def task_deleted():
  task = request.json['task']
  #if there's an incomplete reminder, complete it  
  status = delete_reminder(text=task['text'])
  log("task_deleted: " + str(status))
  if not status: 
    log('failure.')
    return '205'
  rm_db_line(task['id'])
  log(pformat(request.json))
  return '200'

#The homepage uses this to send
#user info back to the server
@app.route('/userdata', methods=['GET', 'POST'])
def store_user_data():
  log("USER DATA")
  params = request.form.to_dict()
  log("params: " + pformat(params))
  if 'huid' not in params or 'htoken' not in params: return '523'
  global userdata
  for k in params.keys():
    userdata[k] = params[k]
  log('userdata: ' + pformat(userdata))
  check = verify_habitica_credentials(id=params['huid'], pwd=params['htoken'])
  if not check: return '500'
  #set habitica creds
  set_env_var('HABITICA_USER', params['huid'], False)
  set_env_var('HABITICA_API_KEY', params['htoken'], False)
  global headers
  test_headers = {
      'x-api-user': params['huid'],
      'x-api-key': params['htoken']
  }
  headers = dc(test_headers)
  init_hooks()
  load_timezone()
  subprocess.call('rm -f '+user, shell=True)
  for k in userdata.keys():
    add_db_line({k:userdata[k]}, user)  
  refresh()
  log("store_user_data " + pformat(userdata['email']))
  return '200' #can't be bool because reasons

#let the client know if they're logged into habitica
@app.route('/check_login', methods=['GET', 'POST'])
def check_login():
  log('check login: ' + str(get_env_var('HABITICA_USER')))
  if get_env_var('HABITICA_USER') and get_env_var('HABITICA_API_KEY'): return '200'
  return '305'

@app.route('/logout', methods=['GET'])
def logout():
  if get_env_var('HABITICA_USER') and get_env_var('HABITICA_API_KEY'):
    rm_env_var('HABITICA_USER')
    rm_env_var('HABITICA_API_KEY')
    return '200'
  return '303'
  
@app.route('/', methods=['GET', 'POST'])
def homepage():
  if not get_env_var('MY_URL'):
    set_env_var('MY_URL', request.url_root)
  return render_template('index.html')

#          FLASK ROUTES
##############################################################
#          MAIN

create_data_dir()
load_user_data()
if __name__ == '__main__':
    app.run(debug=DEBUG)