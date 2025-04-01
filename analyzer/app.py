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

# Load configurations
with open('./config/analyzer/app_conf.yaml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open("./config/log_conf.yaml", "r") as f:
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('analyzerLogger')
logger.debug("Logging is set up...")

# Kafka setup (Global Consumer)
hostname = app_config["events"]["hostname"]
port = app_config["events"]["port"]
client = KafkaClient(hosts=f"{hostname}:{port}")
topic = client.topics[app_config["events"]["topic"].encode()]

consumer = topic.get_simple_consumer(
    consumer_group=b'event_group',
    auto_offset_reset=OffsetType.LATEST,
    reset_offset_on_start=False,  # Do not reset every time
    consumer_timeout_ms=1000
)

# Ensure Kafka consumer is properly closed when app exits
def cleanup_consumer():
    logger.info("Stopping the Kafka consumer")
    consumer.stop()

atexit.register(cleanup_consumer)

# Endpoint functions
def get_listings(index): 
    counter = 0
    for msg in consumer:
        if msg is None:
            break  # Stop if no more messages

        message = msg.value.decode("utf-8")
        data = json.loads(message)

        if data["type"] == "listings":
            if counter == index:
                logger.info("Found message: listing")
                return jsonify([data["payload"]]), 200
            counter += 1

    return {"message": f"No message at index {index}!"}, 404


def get_bids(index): 
    counter = 0
    for msg in consumer:
        if msg is None:
            break  

        message = msg.value.decode("utf-8")
        data = json.loads(message)

        if data["type"] == "bids":
            if counter == index:
                logger.info("Found message: bids")
                return jsonify([data["payload"]]), 200  
            counter += 1

    return {"message": f"No message at index {index}!"}, 404


def get_stats():
    listings_counter = 0
    bids_counter = 0

    for msg in consumer:
        if msg is None:
            break  

        data = json.loads(msg.value.decode("utf-8"))
        if data["type"] == "listings":
            listings_counter += 1
        elif data["type"] == "bids":
            bids_counter += 1

    return {"Listings": listings_counter, "Bids": bids_counter}, 200


app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api("openapi.yaml", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    app.run(port=8200, host="0.0.0.0")