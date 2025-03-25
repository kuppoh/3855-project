import connexion, json, datetime, logging.config, yaml, os, httpx
from datetime import datetime, timezone
from connexion import NoContent
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

with open("./config/log_conf.yaml", "r") as f:
  LOG_CONFIG = yaml.safe_load(f.read())
  logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('processingLogger')

with open("./config/processing/app_conf.yaml", "r") as f:
  app_config = yaml.safe_load(f.read())


DEFAULT = { # use for if file doesn't exist
  "num_listings": 0,
  "num_bids": 0,
  "max_listing_price": 0,
  "max_offer_price": 0,
  "last_updated": "2020-01-01 00:00:00"
}

DATASTORE = app_config['datastore']['filename']

def get_stats():
    # if file doesn't exist, use default values for stats
  if os.path.exists(DATASTORE): 
    with open("/app/data/processing/data.json", "r") as f: 
      data = json.load(f)

    stats = {
      "num_listings": data['num_listings'],
      "num_bids": data['num_bids'],
      "max_listing_price": data['max_listing_price'],
      "max_offer_price": data['max_offer_price']
    }

    logger.debug(f"Contents: {stats}")
    logger.info("Request has been completed...")

    return stats, 200

  else:
    logger.error("Statistics do not exist")
    return 404
# Log a DEBUG message with the contents of the Python Dictionary
# Log an INFO message indicating request has completed


def populate_stats():
  logger.info("Periodic processing has started")

  # Check if the datastore file exists and is not empty
  if not os.path.exists(DATASTORE) or os.stat(DATASTORE).st_size == 0:
    logger.warning("data.json is missing or empty. Initializing with default values.")
    data = {
      "num_listings": 0,
      "num_bids": 0,
      "max_listing_price": 0,
      "max_offer_price": 0,
      "last_updated": "2020-01-01 00:00:00"
    }
    # Create the file with default values
    with open(DATASTORE, "w") as f:
      json.dump(data, f)
    logger.info("data.json created with default values.")
  else:
    try:
      # Load the JSON data from the existing file
      with open(DATASTORE, "r") as f:
        data = json.load(f)
        logger.debug(f"Loaded data from datastore: {data}")
    except json.JSONDecodeError:
      logger.error("Invalid JSON in data.json. Reinitializing with default values.")
      data = {
        "num_listings": 0,
        "num_bids": 0,
        "max_listing_price": 0,
        "max_offer_price": 0,
        "last_updated": "2020-01-01 00:00:00"
      }
      # Reinitialize the file with default values
      with open(DATASTORE, "w") as f:
        json.dump(data, f)
      logger.info("data.json reinitialized with default values.")
  print(f"UMMM: {data}")


  # get current datetime

  curr_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
  #print(curr_date)

  #get datetime of most recent event processed from JSON file... what??

  try:
    last_updated = data['last_updated'] 
  except TypeError:
    last_updated = DEFAULT['last_updated']

  print(last_updated)


  # query the two new GET endpoints from storages service 
  # to get all new events from last datetime you requested them to now

  params = {'start_timestamp': last_updated, 'end_timestamp': curr_date} # so it matches datetime format i used
  print(params)


  r1 = httpx.get(app_config['eventstores']['site_listings']['url'], params=params)

  print(f"Response for get event (get-listing): {r1.status_code}")

  if r1.status_code == 200:
    properties = r1.json()
    #print(f"pleaseeeeeeeeeeeee: {r1.json()}")

    logger.info(f"Received number of events: {len(properties)}")
  else:
    logger.error(f"Cannot retrieve number of events for properties: {r1.status_code}")  
    


  # logger.info(r1)

  r2 = httpx.get(app_config['eventstores']['site_bids']['url'],params=params)

  # logger.info(r2)
  print(f"Response for get event (get-bids): {r2.status_code}")

  if r2.status_code == 200:
    offers = r2.json()
    logger.info(f"Received number of events: {len(offers)}")
  else:
    logger.error(f"Cannot retrieve number of events for offers: {r2.status_code}")
  # log INFO message w/ number of events received for each event type
  # # Log ERROR if you do not get 200 response code

  # based on data, calculate updated statistics

  # num_listings (get number of listings)

  num_listings = len(r1.json())
  data["num_listings"] += num_listings
  

  # num_bids (get number of bids)

  num_bids = len(r2.json())
  data["num_bids"] += num_bids

  # max_listing_price

  listing_stuff = r1.json()
  listing_prices = []

  for row in listing_stuff:
    #print(f"row value: {row}")
    if 'listing_price' in row:
      listing_prices.append(row['listing_price'])
    
  #print(listing_prices)

  #print(max(listing_prices))
  if len(listing_prices) == 0:
      if "max_listing_price" in data:
          max_listing_price = data["max_listing_price"]  # Use previous value
      else:
          max_listing_price = default['max_listing_price']  # Fallback if no previous value
  else:
      max_listing_price = max(listing_prices)

  # max_offer_price

  bid_stuff = r2.json()
  offer_prices = []

  for row in bid_stuff:
    #print(f"row value: {row}")
    if 'offer_price' in row:
      offer_prices.append(row['offer_price'])
  
  if len(offer_prices) == 0:
      if "max_offer_price" in data:
          max_offer_price = data["max_offer_price"]  # Use previous value
      else:
          max_offer_price = default["max_offer_price"]  # Fallback if no previous value
  else:
      max_offer_price = max(offer_prices)

  # write updated statistics to JSON file, including timestamp of most recent event

  updated_data = {
    "num_listings": data['num_listings'],
    "num_bids": data['num_bids'],
    "max_listing_price": max_listing_price,
    "max_offer_price": max_offer_price,
    "last_updated": curr_date
  }
  print(updated_data)

  with open("/app/data/processing/data.json", "w") as f:
    json.dump(updated_data, f)

  # log DEBUG msg with updated stats values

  logger.debug(f"Updated stats values: {updated_data}")

  # Log INFO indicating period processing has ended
  logger.info("Period processing has ended...")




def init_scheduler():
  sched = BackgroundScheduler(daemon=True)
  sched.add_job(populate_stats, 'interval', seconds=app_config['scheduler']['interval'])
  # create another app_config.yaml??
  sched.start()


  
app = connexion.FlaskApp(__name__, specification_dir='') # look at the current directory for OpenAPI Specifications.
app.add_api("openapi.yaml", # OpenAPI file to use
  strict_validation=True, # validate reqs + msgs + params for endpoints against API file
  validate_responses=True) # validate res msgs from endpoints against API file

if __name__ == "__main__":
  #populate_stats()
  init_scheduler()
  #get_stats()
  app.run(port=8100, host="0.0.0.0")