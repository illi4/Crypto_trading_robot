import tweepy
import config
import requests
import os

class tweep(object):
    def __init__(self):
        self.public = ['post']       
        auth = tweepy.OAuthHandler(config.twitter_keys['consumer_key'], config.twitter_keys['consumer_secret'])
        auth.set_access_token(config.twitter_keys['access_token'], config.twitter_keys['access_token_secret'])
        self.api = tweepy.API(auth)
        
    def post(self, message): 
        status = self.api.update_status(status = message) 
        return status

    def post_image(self, url, message):
        filename = 'temp.gif'
        request = requests.get(url, stream=True)
        if request.status_code == 200:
            with open(filename, 'wb') as image:
                for chunk in request:
                    image.write(chunk)

            self.api.update_with_media(filename, status=message)
            os.remove(filename)
        else:
            return "Unable to download image"