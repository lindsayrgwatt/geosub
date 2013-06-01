import tornado.web
from apiclient.discovery import build

import httplib2
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

import json
import store

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

class UserManager(tornado.web.RequestHandler):
  def initialize(self):
    self.store = store.Store("hub/live")

  @classmethod
  def install(cls, handlers):
    handlers.append((r"/user/?(.*)", UserManager))

  def check_xsrf_cookie(self):
    return True

  def post(self, path):
    if path == 'connect':
      try:
        code = self.get_argument("data")
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
      except FlowExchangeError:
        self.set_status(401)
        self.content_type = 'application/json'
        self.write(
            json.dumps('Failed to upgrade the authorization code.'))
        return

      gplus_id = credentials.id_token['sub']
      print "seeing user id " + gplus_id
      if self.store.has(gplus_id, 'users'):
        print "store has user"
        data = self.store.db.execute('select * from users where id=(?)', (gplus_id,)).fetchall();
        self.content_type = 'application/json'
        self.write(json.dumps({'status':'existing', 'uid':gplus_id, 'prefs':data[0][2]}))
      else:
        print "store doesn't have user"
        self.store.db.execute('insert into users (id, credentials) values ((?), (?))', (gplus_id, credentials.to_json()))
        self.store.db.commit()
        self.content_type = 'application/json'
        # TODO: cleanup default prefs.
        self.write(json.dumps({'status':'new','uid': gplus_id,'prefs':"{\"feeds\":{\"feed_construction\":true}}"}))
    elif path == 'sync':
      try:
        token = self.get_argument("token")
        id = self.get_argument("id")
        prefs = self.get_argument("data")
        user_query = self.store.db.execute('select * from users where id=(?)', id).fetchall()
        if len(user_query):
          creds = json.loads(user_query[0][1])
          print creds
          if creds['access_token'] == token:
            return self.sync(id, json.loads(prefs))
        self.write(json.dumps({'status':'error'}))
      except:
        self.write(json.dumps({'status':'error'}))
    else:
      self.write("hello")

  def sync(self, id, prefs):
    print "Syncing " + id
