# TODO
# 1) improve regex for "50$"
# 2) more descriptive logging
# 3) "quarantine" offers that don't make sense or are incomplete

from app import db, app
from app.models import Submission, Offer

from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import os

import praw
import re

APP_ROOT = os.path.dirname(__file__) # refers to application_top
dotenv_path = os.path.join(APP_ROOT, '.env')
load_dotenv(dotenv_path)

gcs = ["Amazon", "Target", "eBay", "Best Buy", "iTunes", "Walmart", "Starbucks", "Disney", "Sephora", "Google Play"] #gift card strings to match on
gcs_regex = "|".join(gcs)

symbols = {"amazon":"AMZN", "target":"TRGT", "ebay":"EBAY", "best buy":"BBY", "itunes":"AAPL", "walmart": "WMT", "starbucks": "SBUX", "disney": "DIS", "sephora": "LVMUY", "google play": "GOOGL"} # "lookup table" for symbols

def getRedditStream():
  try:
      reddit = praw.Reddit(client_id=os.getenv('REDDIT_CLIENT_ID'), client_secret=os.getenv('REDDIT_CLIENT_SECRET'), user_agent='Linux:GCXBot:v0.1 (by /u/chucksaysword)')
      subreddit = reddit.subreddit('giftcardexchange')
      for submission in subreddit.stream.submissions(pause_after=1): #breaks after 1 unsuccessful attempt to pull down new submissions. keeps run time short
        if submission is None:
            break
        elif Submission.query.filter(Submission.reddit_id == submission.id).first() is not None:
          app.logger.info("Submission already processed")
          #upsert record if submission flair/status has changed
          dbSub = Submission.query.filter(Submission.reddit_id == submission.id).first()
          if submission.link_flair_text == 'CLOSED' and dbSub.status == 'active':
            app.logger.info("Updating submission:" + submission.id)
            dbSub.status = 'closed'
            db.session.commit()
          continue
        else:
          app.logger.info("Processing submission: " + submission.id)
          processSubmission(submission)
  except Exception as ex:
        app.logger.exception('Caught an error')

def processSubmission(submission):
  app.logger.info(submission.title)
  createDbSubmission(submission)
  offer = extractOfferFromSubmission(submission)
  if offer is not None:
      createDbOffer(offer)

def createDbSubmission(submission):
    if submission.link_flair_text == 'CLOSED':
        status = 'closed'
    else:
        status = 'active'
    sub = Submission(reddit_id = submission.id,
                     reddit_link = submission.permalink,
                     created_at = datetime.fromtimestamp(submission.created_utc),
                     title = submission.title,
                     status = status)
    try:
        db.session.add(sub)
        db.session.commit()
    except Exception as ex:
        app.logger.exception('Caught an error')


def extractOfferFromSubmission(submission):
  try:
      #extracts text between "[H]" and "[W]" in submission title, this is what the poster has, either "cash" or a giftcard
      have_text = re.search(r"^\[H\](.*).+?(?=\[W\])", submission.title).group(1).strip()
      #extracts text between "[W]" and end of submission title, this is what the poster wants, either "cash" or a giftcard
      want_text = re.search(r"(?<=\[W\]).*", submission.title).group().strip()
      #searches for a known giftcard in the submission's title
      symbol_string = re.search(gcs_regex, submission.title, re.IGNORECASE)
      if symbol_string:
        symbol_string = symbol_string.group().lower()
        #replaces giftcard/store name with corresponding ticker symbol
        symbol = symbols[symbol_string]
      if have_text is not None and want_text is not None:
          offer = {"have" : have_text, "want": want_text}
          if determineBidAsk(offer) == "ask" or determineBidAsk(offer) == "bid" :
              offer["type"] = determineBidAsk(offer)
              offer["price"] = determinePrice(offer)
              offer["quantity"] = determineQuantity(offer)
              offer["symbol"] = symbol
              offer["submission_id"] = submission.id
              #we only want to store offers that make sense
              if 0 < offer["price"] < 1 and offer["quantity"] >= 1:
                  app.logger.info(offer)
                  return offer
                  #createOffer(offer)
  except Exception as ex:
        app.logger.exception('Caught an error')

def determineBidAsk(offer):
  #if giftcard/store name is found in the "have" portion of the submission's title, then the poster is "ask"ing to exchange it for cash
  if len(re.findall(gcs_regex, offer["have"], re.IGNORECASE)) > 0:
    return "ask"
  #if giftcard/store name is found in the "want" portion of the submission's title, then the poster is "bid"ding on it w/ cash
  elif len(re.findall(gcs_regex, offer["want"], re.IGNORECASE)) > 0:
    return "bid"

def determinePrice(offer):
  #price is expressed as how much a poster will accept for $1 of giftcard face value and is always between $0.00 and $1.00
  try:
      #price expressed as a percentage
      if offer["type"] == 'ask' and '%' in offer["want"]:
        price = float(re.search(r"(\d+(\.\d+)?)", offer["want"]).group())/100
      elif offer["type"] == 'bid' and '%' in offer["have"]:
        price = float(re.search(r"(\d+(\.\d+)?)", offer["have"]).group())/100
      #if price is given in dollars, we convert to percentage
      elif offer["type"] == 'ask' and '$' in offer["want"] and '$' in offer["have"]:
        price = float(re.search(r"(?:[\$]{1}[\d]+.*?\d*)", offer["want"]).group().strip('$').replace(',',''))/float(re.search(r"(?:[\$]{1}[\d]+.*?\d*)", offer["have"]).group().strip('$').replace(',',''))
      elif offer["type"] == 'bid' and '$' in offer["have"] and '$' in offer["want"]:
        price = float(re.search(r"(?:[\$]{1}[\d]+.*?\d*)", offer["have"]).group().strip('$').replace(',',''))/float(re.search(r"(?:[\$]{1}[\d]+.*?\d*)", offer["want"]).group().strip('$').replace(',',''))
      #if no price is given, we set to 0 and later discard
      else:
        price = 0

      return price
  except Exception as ex:
    app.logger.exception('Caught an error')

def determineQuantity(offer):
#quantity is equivalent to the face value (rounded to the nearest dollar) of the giftcard being traded
  try:
      if offer["type"] == 'ask' and '$' in offer["have"]:
        quantity = round(float(re.search(r"(?:[\$]{1}[\d]+.*?\d*)", offer["have"]).group().strip('$')))
      elif offer["type"] == 'bid' and '$' in offer["want"]:
        quantity = round(float(re.search(r"(?:[\$]{1}[\d]+.*?\d*)", offer["want"]).group().strip('$')))
      #if no quantity is given, we set to 0 and later discard
      else:
        quantity = 0

      return quantity
  except Exception as ex:
    app.logger.exception('Caught an error')

def createDbOffer(offer):
    offer = Offer(type = offer["type"],
                     qty = offer["quantity"],
                     price = offer["price"],
                     symbol = offer["symbol"],
                     submission_id = offer["submission_id"])
    try:
        db.session.add(offer)
        db.session.commit()
    except:
        raise

def lambda_handler(event, context):
    getRedditStream()

#def main():
#  getRedditStream()

#if __name__ == "__main__":
#    main()
