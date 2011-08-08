from google.appengine.ext import db

   
class User(db.Model):
    user              = db.UserProperty()
    userID            = db.StringProperty()
    activated         = db.BooleanProperty()

    name              = db.StringProperty()
    nickname          = db.StringProperty()
    phone_number      = db.StringProperty()

    verification_code = db.StringProperty()
    createDate        = db.DateTimeProperty(auto_now_add=True)

class Voicemail(db.Model):
    user        = db.ReferenceProperty(User)
    user_number = db.StringProperty()

    from_number = db.StringProperty()

    create_date = db.DateTimeProperty(auto_now_add=True)
    
    voicemail_url = db.StringProperty()
    voicemail_duration = db.IntegerProperty()
    twilio_sid    = db.StringProperty()