import connexion, json, datetime, logging.config, yaml, pykafka, sys
from datetime import datetime
from connexion import NoContent
from database import make_session
from sqlalchemy import select
from models import listings, bids, Base
from pykafka import KafkaClient
from pykafka.common import OffsetType
from threading import Thread
from commands import create_tables, drop_tables  # Import the database stuff
from database import engine

with open('./config/storage/app_conf.yaml', 'r') as f:
  app_config = yaml.safe_load(f.read())

with open("./config/log_conf.yaml", "r") as f:
  LOG_CONFIG = yaml.safe_load(f.read())
  logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('storageLogger')


def process_messages():

  hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}" # kafka:9092

  logger.info(f"connecting to kafka: {app_config['events']['hostname']}:{app_config['events']['port']}.")

  client = KafkaClient(hosts=hostname)
  # client = KafkaClient(hosts=f"{app_config['events']['hostname']}:{app_config['events']['port']}")
  topic = client.topics[str.encode(app_config['events']['topic'])]

  # Create a consume on a consumer group, that only reads new messages
  # (uncommitted messages) when the service re-starts (i.e., it doesn't
  # read all the old messages from the history in the message queue).
  consumer = topic.get_simple_consumer(consumer_group=b'event_group', reset_offset_on_start=False, auto_offset_reset=OffsetType.LATEST)

  logger.info("Consumer created. Waiting for messages...")

  # This is blocking - it will wait for a new message
  for msg in consumer:
    msg_str = msg.value.decode('utf-8')
    msg = json.loads(msg_str)
    logger.info("Message: %s" % msg)
    payload = msg["payload"]
    
    if msg["type"] == "listings": # Change this to your event type
    # Store the event1 (i.e., the payload) to the DB
      logger.info("Processing listings event: %s", payload)
      post_listing(payload)
    elif msg["type"] == "bids": # Change this to your event type
    # Store the event2 (i.e., the payload) to the DB
    # Commit the new message as being read
      logger.info("Processing bids event: %s", payload)
      post_bid(payload)
    consumer.commit_offsets()


def post_listing(body): # post listings

  obj = listings(
    listing_id=body["listing_id"], 
    listing_price=body["listing_price"], 
    # listing_post=body["listing_post"],
    listing_type=body["listing_type"], 
    listing_status=body["listing_status"], 
    listing_contact=body["listing_contact"],
    trace_id=body["trace_id"])

  print(f"Inserting listing with status: {body['listing_status']}")

  logger.debug(f"Stored event: listing-post-event, with trace_id: {obj.trace_id}")

  session = make_session()
  session.add(obj)
  session.commit()
  session.close()
  
  return NoContent, 201


def post_bid(body): # post bids/offers

  obj = bids(
    bidding_id=body["bidding_id"], 
    listing_id=body["listing_id"], 
    asking_price=body["asking_price"], 
    offer_price=body["offer_price"], 
    # offer_date=body["offer_date"],
    property_square_feet=body["property_square_feet"], 
    price_per_square_feet=body["price_per_square_feet"], 
    bid_status=body["bid_status"],
    trace_id=body["trace_id"])

  # after creating and storing things into obj, log the event (log)
  logger.debug(f"Stored event: bids-post-event, with trace_id: {obj.trace_id}")

  session = make_session()
  session.add(obj)
  session.commit()
  session.close()

  return NoContent, 201


def get_listings(start_timestamp, end_timestamp): # get the property listings
  # going to have to pass it like: 2025-02-06 20:20:53, 2025-02-06 20:21:05 (without the T, and z)
  session = make_session()

  start = datetime.strptime(start_timestamp, "%Y-%m-%d %H:%M:%S") # time format is the same as 2025-02-06 20:21:05, the T: separator, and z: is UTC
  end = datetime.strptime(end_timestamp, "%Y-%m-%d %H:%M:%S") 

  statement = select(listings).where(listings.listing_post >= start).where(listings.listing_post < end)

  result = [ # created dictionary for output 
      { # "row.*whatever" is us accessing the columns from that row
          "listing_id": row.listing_id,
          "listing_price": row.listing_price,
          "listing_post": row.listing_post,
          "listing_type": row.listing_type,
          "listing_status": row.listing_status.value,  
          "listing_contact": row.listing_contact,
          "trace_id": row.trace_id
      }
      for row in session.execute(statement).scalars().all() 
      # gets what we are looking for instead of the whole row
  ]

  session.close()

  logger.info("Found %d listings (start: %s | end: %s)", len(result), start, end)
  return result


def get_bids(start_timestamp, end_timestamp): # get the list of bids/offers
  session = make_session()

  start = datetime.strptime(start_timestamp, "%Y-%m-%d %H:%M:%S")
  end = datetime.strptime(end_timestamp, "%Y-%m-%d %H:%M:%S")

  statement = select(bids).where(bids.offer_date >= start).where(bids.offer_date < end)

  result = [ # created dictionary for output 
      {
          "bidding_id": row.bidding_id,
          "listing_id": row.listing_id,
          "asking_price": row.asking_price,
          "offer_price": row.offer_price,
          "offer_date": row.offer_date,
          "property_square_feet": row.property_square_feet,
          "price_per_square_feet": row.price_per_square_feet,
          "bid_status": row.bid_status.value, 
          "trace_id": row.trace_id
      }
      for row in session.execute(statement).scalars().all()
  ]

  session.close()

  logger.info("Found %d listings (start: %s | end: %s)", len(result), start, end)
  return result

def setup_kafka_thread():
  logger.info("setting up kafka consumer thread")
  t1 = Thread(target=process_messages)
  t1.setDaemon(True)
  t1.start()
  logger.info("consumer setup done.")

app = connexion.FlaskApp(__name__, specification_dir='') # look at the current directory for OpenAPI Specifications.
app.add_api("openapi.yaml", # OpenAPI file to use
  strict_validation=True, # validate reqs + msgs + params for endpoints against API file
  validate_responses=True) # validate res msgs from endpoints against API file

if __name__ == "__main__":
  if len(sys.argv) > 1 and sys.argv[1] == "reset":
    logger.info("Dropping tables...")
    drop_tables()

    logger.info("Creating tables for reset...")
    create_tables()
  else: 
    logger.info("Creating tables...")
    create_tables()

  setup_kafka_thread()  # Set up Kafka consumer thread
  app.run(port=8090, host="0.0.0.0")