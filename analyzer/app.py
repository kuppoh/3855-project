import connexion, json, datetime, logging.config, yaml, pykafka
from flask import jsonify
from datetime import datetime
from connexion import NoContent, FlaskApp
from sqlalchemy import select
from pykafka import KafkaClient
from pykafka.common import OffsetType
from threading import Thread

from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

app = FlaskApp(__name__)

app.add_middleware(
  CORSMiddleware,
  position=MiddlewarePosition.BEFORE_EXCEPTION,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

with open('./config/analyzer/app_conf.yaml', 'r') as f:
  app_config = yaml.safe_load(f.read())

with open("./config/log_conf.yaml", "r") as f:
  LOG_CONFIG = yaml.safe_load(f.read())
  logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('analyzerLogger')

logger.debug("logging is set up...")

#####
hostname = app_config["events"]["hostname"]
port = app_config["events"]["port"]
client = KafkaClient(hosts=f"{hostname}:{port}")
topic = client.topics[app_config["events"]["topic"].encode()]
consumer = topic.get_simple_consumer(
    consumer_group=b'event_group',  
    reset_offset_on_start=True, 
    consumer_timeout_ms=1000
)
#####

def get_listings(index): # get the property listings
  # consumer = topic.get_simple_consumer(reset_offset_on_start=True, consumer_timeout_ms=1000)
  counter = 0

  for msg in consumer:
    message = msg.value.decode("utf-8")
    data = json.loads(message)

    if data["type"] == "listings": 
      if counter == index:
        logger.info("found message: listing")
        return jsonify([data["payload"]]), 200
      counter += 1
  return { "message": f"No message at index {index}!"}, 404


def get_bids(index): 
  # consumer = topic.get_simple_consumer(reset_offset_on_start=True, consumer_timeout_ms=1000)
  counter = 0

  for msg in consumer:
    message = msg.value.decode("utf-8")
    data = json.loads(message)

    if data["type"] == "bids": 
      if counter == index:
        logger.info("found message: bids")
        return jsonify([data["payload"]]), 200 # it was not an array, so i had to make the return message an array, due to app_config constraints
      counter += 1
  return { "message": f"No message at index {index}!"}, 404

def get_stats():
  # consumer = topic.get_simple_consumer(consumer_group=b'event_group', reset_offset_on_start=True, consumer_timeout_ms=1000)
  listings_counter = 0
  bids_counter = 0
  
  for msg in consumer:
    data = json.loads(msg.value.decode("utf-8"))
    if data["type"] == "listings":
      listings_counter += 1
    elif data["type"] == "bids":
      bids_counter += 1

  return {"Listings": listings_counter, "Bids": bids_counter}, 200

app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api("openapi.yaml", # OpenAPI file to use
  strict_validation=True, # validate reqs + msgs + params for endpoints against API file
  validate_responses=True) # validate res msgs from endpoints against API file


if __name__ == "__main__":
  app.run(port=8200, host="0.0.0.0")