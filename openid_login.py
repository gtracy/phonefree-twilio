#!/usr/bin/env python

import os
import logging
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

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
class OpenIdLoginHandler(webapp.RequestHandler):
  def get(self):
      results = []
      for p in openIdProviders:
          p_name = p.split('.')[0] # take "AOL" from "AOL.com"
          p_url = p.lower()        # "AOL.com" -> "aol.com"
          results.append({'name':p_name,
                          'url':users.create_login_url(federated_identity=p_url),
                          'image':buttons[p_name],
                          })
          #self.response.out.write('[<a href="%s">%s</a>]' % 
          #                        (users.create_login_url(federated_identity=p_url), p_name))

      template_values = {'endpoints':results}
      path = os.path.join(os.path.dirname(__file__), 'openid-login.html')
      self.response.out.write(template.render(path, template_values))

def main():
    application = webapp.WSGIApplication([('/_ah/login_required', OpenIdLoginHandler),
                                         ],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
