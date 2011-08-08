#!/usr/bin/env python

import os
import logging

from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.db import Key
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

from google.appengine.api import users
from google.appengine.api import mail
from google.appengine.api import memcache

from google.appengine.runtime import apiproxy_errors

from dataModel import *


class BaseHandler(webapp.RequestHandler):
    @property
    def current_user(self):
        if users.get_current_user():
            user = users.get_current_user()
            localUser = db.GqlQuery("select * from User where userID = :1", user.user_id()).get()
            if not localUser:
                user = User(userID=user.user_id(),
                            nickname=user.nickname(),
                            activated=False)
                user.put()
                self.redirect('/') #user/edit?userKey=%s' % user.key())
            else:
                user = localUser
            self._current_user = user
        else:
            self._current_user = None

        return self._current_user


class UserEditHandler(BaseHandler):
    
    def get(self):
        user = self.current_user
        if user:
            logging.info("User: %s", user.nickname)
            greeting = '<a href="%s">sign out</a>' % users.create_logout_url("/")
        
            nickname = first + ' ' + last if user.nickname is None else user.nickname
            email = user.email if user.preferredEmail is None else user.preferredEmail
        else:
            greeting = ''
            nickname = ''
            email = ''
            
        template_values = {'nickname':nickname,
                           'preferredEmail':email,
                           'greeting':greeting,
                           'userKey':self.request.get('userKey'),
                          }
        path = os.path.join(os.path.dirname(__file__), 'profile.html')
        self.response.out.write(template.render(path, template_values))
        
## end UserEditHandler

class ProfileAjaxUpdateHandler(webapp.RequestHandler):

    def post(self):
        activeUser = users.get_current_user()
        if activeUser is None:
            self.redirect("/")
            return

        userKey = self.request.get('userKey')
        
        user = db.get(userKey)
        if user is None:
            logging.error("Profile update attempt with no logged in user. This should never happen, %s" % userKey)
            return
        
        logging.info("Updating profile for %s with %s, %s, %s, %s" % (userKey,first,last,nickname,email))
        user.put()
        
        self.redirect('/')

## end ProfileAjaxUpdateHandler


def getUser(userID):
    
    user = memcache.get(userID)
    if user is None:
      userQuery = db.GqlQuery("SELECT * FROM User WHERE userID = :1", userID)
      users = userQuery.fetch(1)
      if len(users) == 0:
          logging.info("We can't find this user in the User table... userID: %s" % userID)
          return None
      else:
          memcache.set(userID, user)
          return users[0]
    else:
      return user
    
## end getUser()

def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/user', UserHandler),
                                        ('/user/edit', UserEditHandler),
                                        ('/user/update', ProfileAjaxUpdateHandler),
                                        ],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
