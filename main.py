import os
import logging
from random import randint

from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util
from google.appengine.api import users
from google.appengine.ext import webapp

from dataModel import *
from twilio.util import TwilioCapability
from twilio import twiml, TwilioRestException
from twilio.rest import TwilioRestClient
import open_id_user

import configuration

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

class MainHandler(open_id_user.BaseHandler):
    def get(self):
      # force the user to login and get their user model
      user = self.current_user
      if user:
          login = ('%s (<a href="%s">sign out</a>)' % (user.nickname, users.create_logout_url("/")))
      else:
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
          self.response.out.write(template.render(path, template_values))
          return
       
      # check the site to determine if the site has been authorized. 
      # if so, look at the user model to see if they are the owner
      # if not, offer the user the ability to authorize the site (this should only happen once)
      capability = TwilioCapability(configuration.TWILIO_ACCOUNT_SID,configuration.TWILIO_AUTH_TOKEN)
      if user.activated is False:
          owner = db.GqlQuery("select * from User where activated = True").get()
          if owner is None:
              # start the owner verification sequence. 
              code = randint(10000,99999)
              user.verification_code = str(code)
              user.put()
              sendSMS(configuration.SMS_VERIFICATION_PHONE,
                      'Enter this five digit code in the browser to validate your account %s'%str(code))
              template_file = 'templates/owner_verification.html'
          else:
              # this isn't the owner so they only get the one big button to call the owner
              template_file = 'templates/friend.html'
      else:
          # if the owner of the site is logged in, create a dialing interface.
          # the owner has liberal capabilities
          capability.allow_client_incoming("owner")
          template_file = 'templates/owner.html'
      
      # now make sure the twilio configuration is correct
      if validateTwilio() is False:
        self.redirect('/error.html')
        return
      
      # generate the token based on the configured capabilities.
      # everyone can call out, but only the owner can accept incoming calls.
      capability.allow_client_outgoing(configuration.TWILIO_APP_SID)
      token = capability.generate()
 
      template_values = {'token':token,
                         'client':'owner',
                         'login':login,
                         'current_user':user.nickname,
                         'google_analytics':configuration.GOOGLE_ANALYTICS_CODE,
                         'name':configuration.MY_NAME,
                         'title':configuration.APP_TITLE,
                        }
      
      # generate the html
      path = os.path.join(os.path.dirname(__file__), template_file)
      self.response.out.write(template.render(path, template_values))

## end MainHandler

class InboundHandler(webapp.RequestHandler):
    def post(self):
    
        # check to see if the owner is logged in. if they are, route
        # the call via the client interface
        template_vals = {'client':'owner',}
        
        path = os.path.join(os.path.dirname(__file__), 'templates/inbound.xml')
        self.response.headers['Content-Type'] = "text/xml; charset=utf-8"
        self.response.out.write(template.render(path, template_vals))

## end InboundHandler

class InboundCompleteHandler(webapp.RequestHandler):
    def post(self):
        # send the caller to voicemail if there was a timeout
        logging.debug('inbound call complete.')
        logging.debug('... CallStatus : %s' % self.request.get('CallStatus'))
        logging.debug('... DialCallStatus : %s' % self.request.get('DialCallStatus'))
        if self.request.get('DialCallStatus') is 'no-answer':
            callback_url = 'http://'+configuration.APP_ENGINE_ID+'.appspot.com/voicemail/callback'
            template_vals = {'action_url':callback_url,}
            path = os.path.join(os.path.dirname(__file__), 'templates/voicemail.xml')
            self.response.headers['Content-Type'] = 'text/xml; charset=utf-8'
            self.response.out.write(template.render(path, template_vals))
            return
            
        # else, ignore it and end the call
        template_vals = {}
        path = os.path.join(os.path.dirname(__file__), 'templates/hangup.xml')
        self.response.headers['Content-Type'] = 'text/xml; charset=utf-8'
        self.response.out.write(template.render(path,template_vals))
        return
        
## end InboundCompleteHandler

class OutboundHandler(webapp.RequestHandler):
    """ Primary handler for calls created by a browser.
        It could come from the owner or a friend.
        If it is the latter, the call must go to the owner's browser
    """
    def post(self):
        # if a friend is calling, the number will start with 'client'
        number = self.request.get('number')
        if number.find('client') > -1:
            # a friend is initiating a call from a browser
            friend = self.request.get('nickname')
            logging.debug('%s is trying to call from another browser.' % friend)
            template_vals = {'caller_id':friend,
                             'client':'owner',}
            template_file = 'templates/outbound_browser.xml'
        else:
            # someone is calling from an external number. now it's
            # time to send the call to the owner's browser
            logging.debug('new outbound call from owner to %s' % number)
            template_vals = {'caller_id':configuration.TWILIO_CALLER_ID,
                             'phone':number,}
            template_file = 'templates/outbound.xml'
        
        
        path = os.path.join(os.path.dirname(__file__), template_file)
        self.response.headers['Content-Type'] = "text/xml; charset=utf-8"
        self.response.out.write(template.render(path, template_vals))

## end OutboundHandler
        
class VoicemailCallbackHandler(webapp.RequestHandler):
    def post(self):
        # verify that this is coming from Twilio
        
        # shove the recording in the datastore
        user_phone = self.request.get('To')
        user = db.GqlQuery("select * from User where phone_number = :1", user_phone).get()
        if user is None:
          # this is impossible
          logging.error('Configuration bork... we have a voicemail for a user (%s) that does not exist' % user_phone)
        else:
          voicemail = Voicemail()
          voicemail.user_number = user_phone
          voicemail.from_number = self.request.get('From')
          voicemail.twilio_sid = self.request.get('CallSid')
          voicemail.voicemail_url = self.request.get('RecordingUrl')
          voicemail.voicemail_duration = int(self.request.get('RecordingDuration'))
          voicemail.put()
          
          # send the user an SMS message to let them know about the message
          
class VerifyUserHandler(open_id_user.BaseHandler):
    def post(self):
        # force the user to login and get their user model
        user = self.current_user
        if user is None:
            self.redirect('/')
            return
            
        code = self.request.get('code')
        
        if user.verification_code != code:
            logging.error('illegal verification code entered!')
            # return error json
        else:
            # return success json
            success = True
            
        user.activated = True
        user.put()
        
        # return json response
        self.redirect('/')

## end RegisterHandler


def sendSMS(phone,msg):
    """
    Convenience method to send an SMS
    """
    try:
        return
        client = TwilioRestClient(configuration.TWILIO_ACCOUNT_SID,
                                  configuration.TWILIO_AUTH_TOKEN)
        logging.debug('sending message - %s - to %s' % (msg,phone))
        message = client.sms.messages.create(to=phone,
                                             from_=configuration.TWILIO_CALLER_ID,
                                             body=msg)
    except TwilioRestException,te:
        logging.error('Unable to send SMS message! %s'%te)
        
## end sendSMS()

def validateTwilio():
    """ Verifies the configured Twilio account. If the REST call fails
        we assume it is misconfigured
    """
    try:
      conn = TwilioRestClient(configuration.TWILIO_ACCOUNT_SID,configuration.TWILIO_AUTH_TOKEN)
      account = conn.accounts.get(configuration.TWILIO_ACCOUNT_SID)
    except: 
      #logging.error("Twilio account validation failed for ACCOUNT SID %s" % configuration.TWILIO_ACCOUNT_SID)
      return False
      
    if account is None:
        return False
    else:
        return True
## end validateTwilio()

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    application = webapp.WSGIApplication([('/', MainHandler),
                                          ('/inbound', InboundHandler),
                                          ('/inbound/complete', InboundCompleteHandler),
                                          ('/outbound', OutboundHandler),
                                          ('/verify', VerifyUserHandler),
                                          ('/voicemail/callback',VoicemailCallbackHandler),
                                         ],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
