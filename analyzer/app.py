import connexion, json, datetime, logging.config, yaml, os, time
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



def consumer_polling():
    logger.debug("Starting persistent consumer...")
    consumer = create_consumer()

    consumer.subscribe(
        [topic_name],
        on_assign=lambda c, partitions: logger.debug(f"Assigned partitions: {partitions}"),
        on_revoke=lambda c, partitions: logger.debug(f"Revoked partitions: {partitions}")
    )

    while True:  # Continuously poll for messages
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            logger.debug("No messages fetched in this poll cycle.")
            continue

        if msg.error():
            logger.error(f"Consumer error: {msg.error()}")
            continue

        data = json.loads(msg.value().decode("utf-8"))
        logger.debug(f"Processing message: {data}")

        # Add logic to process the message (e.g., save it to a database or update counters)

    consumer.close()  # Ensures the consumer is closed when the polling stops
    logger.debug("Consumer closed after polling.")


def get_stats():
    logger.debug("Creating consumer for stats...")
    consumer = create_consumer()
    consumer.subscribe(
        [topic_name],
        on_assign=lambda c, partitions: logger.debug(f"Assigned partitions: {partitions}"),
        on_revoke=lambda c, partitions: logger.debug(f"Revoked partitions: {partitions}")
    )

    listings_counter = 0
    bids_counter = 0

    # Set a timeout duration (e.g., 10 seconds)
    timeout_duration = 10  # Adjust based on your needs
    start_time = time.time()

    while True:
        # Check if the timeout has been exceeded
        if time.time() - start_time > timeout_duration:
            logger.debug("Timeout reached, exiting polling loop.")
            break

        msg = consumer.poll(timeout=1.0)
        logger.debug(f"Assigned partition: {consumer.assignment()}")

        if msg is None:
            logger.debug("No messages fetched in this poll cycle.")
            continue  # Continue polling until timeout

        if msg.error():
            logger.error(f"Consumer error: {msg.error()}")
            continue  # Skip errors and continue polling

        # Parse and process the message
        try:
            data = json.loads(msg.value().decode("utf-8"))
            logger.debug(f"Processing message: {data}")

            # Update counters based on message type
            if data["type"] == "listings":
                listings_counter += 1
                logger.debug(f"Incremented listings_counter: {listings_counter}")
            elif data["type"] == "bids":
                bids_counter += 1
                logger.debug(f"Incremented bids_counter: {bids_counter}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {msg.value()} - {e}")
            continue  # Skip invalid messages

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
    consumer_thread = Thread(target=get_stats, daemon=True)
    consumer_thread.start()

    app.run(port=8200, host="0.0.0.0")