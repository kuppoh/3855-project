import connexion, json, datetime, logging.config, yaml, os
from flask import jsonify
from datetime import datetime
from connexion import NoContent, FlaskApp
from sqlalchemy import select
from confluent_kafka import Consumer, Producer
from threading import Thread

from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

# Load configurations
with open('./config/analyzer/app_conf.yaml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open("./config/log_conf.yaml", "r") as f:
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('analyzerLogger')
logger.debug("Logging is set up...") 

# Kafka setup
hostname = app_config['events']['hostname']
port = app_config['events']['port']
topic_name = app_config["events"]["topic"]

kafka_config = {
    'bootstrap.servers': f"{hostname}:{port}",
    'group.id': 'analyzer_group', # needed...
    'auto.offset.reset': 'earliest'
}

# Create a global Kafka consumer
def create_consumer():
    return Consumer(kafka_config)

# Endpoint functions
def get_listings(index):
    logger.debug("Creating consumer for listings...")
    consumer = create_consumer()
    consumer.subscribe([topic_name])
    logger.debug(f"Consumer assignment: {consumer.assignment()}")

    msg = consumer.poll(timeout=1.0)  # Poll once
    if msg is None:
        logger.debug("No message received.")
        consumer.close()
        logger.debug("Consumer closed for get-listings successfully!")
        return {"message": f"No message at index {index}!"}, 404

    if msg.error():
        logger.error(f"Consumer error: {msg.error()}")
        consumer.close()
        logger.debug("Consumer closed for get-listings successfully!")
        return {"message": "Error consuming message!"}, 500

    message = msg.value().decode('utf-8')
    data = json.loads(message)

    if data["type"] == "listings":
        logger.info("Found message: listing")
        consumer.close()
        logger.debug("Consumer closed for get-listings successfully!")
        return jsonify([data["payload"]]), 200

    logger.debug("Message type is not 'listings' or wrong index.")
    consumer.close()
    logger.debug("Consumer closed for get-listings successfully!")
    return {"message": f"No message at index {index}!"}, 404


def get_bids(index):
    logger.debug("Creating consumer for bids...")
    consumer = create_consumer()
    consumer.subscribe([topic_name])
    logger.debug(f"Consumer assignment: {consumer.assignment()}")

    msg = consumer.poll(timeout=1.0)  # Poll once
    if msg is None:
        logger.debug("No message received.")
        consumer.close()
        logger.debug("Consumer closed for get-bids successfully!")
        return {"message": f"No message at index {index}!"}, 404

    if msg.error():
        logger.error(f"Consumer error: {msg.error()}")
        consumer.close()
        logger.debug("Consumer closed for get-bids successfully!")
        return {"message": "Error consuming message!"}, 500

    message = msg.value().decode('utf-8')
    data = json.loads(message)

    if data["type"] == "bids":
        logger.info("Found message: bids")
        consumer.close()
        logger.debug("Consumer closed for get-bids successfully!")
        return jsonify([data["payload"]]), 200

    logger.debug("Message type is not 'bids' or wrong index.")
    consumer.close()
    logger.debug("Consumer closed for get-bids successfully!")
    return {"message": f"No message at index {index}!"}, 404


def get_stats():
    logger.debug("Creating consumer for stats...")
    consumer = create_consumer()
    consumer.subscribe([topic_name])
    logger.debug(f"Consumer assignment: {consumer.assignment()}")

    listings_counter = 0
    bids_counter = 0

    while True:  # Continuously poll for messages
        msg = consumer.poll(timeout=1.0)

        if msg is None:
            logger.debug("No more messages available.")
            break  # Exit the loop when no more messages are fetched

        if msg.error():
            logger.error(f"Consumer error: {msg.error()}")
            continue  # Skip errors and move on to the next poll

        # Parse the message
        data = json.loads(msg.value().decode("utf-8"))
        logger.debug(f"Processing message: {data}")

        # Update counters based on message type
        if data["type"] == "listings":
            listings_counter += 1
            logger.debug(f"Incremented listings_counter: {listings_counter}")
        elif data["type"] == "bids":
            bids_counter += 1
            logger.debug(f"Incremented bids_counter: {bids_counter}")

    consumer.close()
    logger.debug("Consumer closed for get-stats successfully!")
    return {"Listings": listings_counter, "Bids": bids_counter}, 200

app = connexion.FlaskApp(__name__, specification_dir='')

if "CORS_ALLOW_ALL" in os.environ and os.environ["CORS_ALLOW_ALL"] == "yes":
    app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_api("openapi.yaml", base_path="/analyzer", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    app.run(port=8200, host="0.0.0.0")