import connexion, json, datetime, logging.config, yaml, os, time
from flask import jsonify
from datetime import datetime
from connexion import NoContent, FlaskApp
from sqlalchemy import select
from confluent_kafka import Consumer, Producer
from threading import Thread, Lock

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

print(f'{hostname}:{port}')

kafka_config = {
    'bootstrap.servers': f'{hostname}:{port}',
    'group.id': 'analyzer_group',
    'auto.offset.reset': 'earliest',  # Start consuming from the beginning
    'enable.auto.commit': True
}


# Create a global Kafka consumer
def create_consumer():
    return Consumer(kafka_config)



# Endpoint functions
def get_listings(index):
    logger.debug("Creating consumer for listings...")
    consumer = create_consumer()
    consumer.subscribe([topic_name])
    msg = consumer.poll(timeout=1.0)  # Poll once
    logger.debug(f"Consumer assignment: {consumer.assignment()}")

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
    msg = consumer.poll(timeout=1.0)  # Poll once    
    logger.debug(f"Consumer assignment: {consumer.assignment()}")

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

listings_counter = 0
bids_counter = 0
counter_lock = Lock()

def consumer_polling():
    global listings_counter, bids_counter
    logger.debug("Starting persistent consumer...")
    consumer = create_consumer()
    consumer.subscribe([topic_name])

    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            logger.debug("No messages fetched in this poll cycle.")
            continue

        if msg.error():
            if isinstance(msg.error(), KafkaException):
                logger.error(f"Consumer error: {msg.error()}")
            continue

        raw_value = msg.value().decode("utf-8")
        logger.debug(f"Raw message received: {raw_value}")
        data = json.loads(raw_value)

        msg_type = data.get("type")
        if not msg_type:
            logger.warning("Message missing 'type' field.")
            continue

        with counter_lock:
            logger.debug(f"Inside lock: Listings={listings_counter}, Bids={bids_counter}")
            if msg_type == "listings":
                listings_counter += 1
                logger.info(f"Listings counter incremented: {listings_counter}")
            elif msg_type == "bids":
                bids_counter += 1
                logger.info(f"Bids counter incremented: {bids_counter}")
            else:
                logger.warning(f"Unknown message type: {msg_type}")

def get_stats():
    logger.debug("Fetching stats...")

    # Sleep to give the consumer time to update the counters
    time.sleep(0.5)

    with counter_lock:
        logger.debug(f"Returning stats: Listings={listings_counter}, Bids={bids_counter}")
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
    consumer_thread = Thread(target=consumer_polling, daemon=True)
    consumer_thread.start()

    app.run(port=8200, host="0.0.0.0")