import os
import logging
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

import configuration
from dataModel import User

openIdProviders = (
    'Google.com/accounts/o8/id', # shorter alternative: "Gmail.com"
    'Yahoo.com',
    'AOL.com',
    # add more here
)

# note that these keynames must match the provider names in front
# of the .com names above
buttons = {'Google':'/img/googleButton.png',
           'Yahoo':'/img/yahooButton.png',
           'AOL':'/img/aolButton.png',
          }
          

class BaseHandler(webapp.RequestHandler):
    """ 
    Base class to help manage user login
    """
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

    @property
    def user_login_page(self):
          greeting = ''
          results = []
          for p in openIdProviders:
              p_name = p.split('.')[0] # take "AOL" from "AOL.com"
              p_url = p.lower()        # "AOL.com" -> "aol.com"
              logging.debug('name %s, url %s' % (p_name,p_url))
              results.append({'name':p_name,
                              'url':users.create_login_url(federated_identity=p_url,dest_url="/"),
                              'image':buttons[p_name],
                              })

          # generate the html
          template_values = {'greeting':greeting,
                             'endpoints':results,
                             'app_title':configuration.APP_TITLE,
                             'app_description':configuration.APP_DESCRIPTION,
                             'owner_name':configuration.MY_NAME,
                             }
          path = os.path.join(os.path.dirname(__file__), 'templates/splash.html')
          return(template.render(path, template_values))

