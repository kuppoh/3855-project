import connexion
import json
import logging.config
import yaml
import os
import time
from flask import jsonify
from threading import Thread, Lock
from confluent_kafka import Consumer, KafkaException
from queue import Queue
from starlette.middleware.cors import CORSMiddleware
from connexion.middleware import MiddlewarePosition

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
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': True,
    'session.timeout.ms': 30000
}

# Create a global Kafka consumer and message queue
message_queue = Queue()
counter_lock = Lock()
listings_counter = 0
bids_counter = 0

# Global consumer
consumer = Consumer(kafka_config)
consumer.subscribe([topic_name])

def consumer_polling():
    global listings_counter, bids_counter
    logger.debug("Starting persistent consumer...")
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
            elif msg_type == "bids":
                bids_counter += 1

        # Place message into the queue
        message_queue.put(data)

def get_listings(index):
    global listings_counter
    with counter_lock:
        if index >= listings_counter:
            logger.debug("Index out of range for listings.")
            return {"message": f"No message at index {index}!"}, 404

    counter = 0
    while not message_queue.empty():
        message = message_queue.get_nowait()  # Non-blocking
        if message["type"] == "listings":
            if counter == index:
                return jsonify([message["payload"]]), 200
            counter += 1
    return {"message": f"No message at index {index}!"}, 404

def get_bids(index):
    global bids_counter
    with counter_lock:
        if index >= bids_counter:
            logger.debug("Index out of range for bids.")
            return {"message": f"No message at index {index}!"}, 404

    counter = 0
    while not message_queue.empty():
        message = message_queue.get_nowait()  # Non-blocking
        if message["type"] == "bids":
            if counter == index:
                return jsonify([message["payload"]]), 200
            counter += 1
    return {"message": f"No message at index {index}!"}, 404

def get_stats():
    logger.debug("Fetching stats...")
    with counter_lock:
        logger.debug(f"Returning stats: Listings={listings_counter}, Bids={bids_counter}")
        return {"Listings": listings_counter, "Bids": bids_counter}, 200

# Setup Connexion app
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

# Start consumer thread
consumer_thread = Thread(target=consumer_polling, daemon=True)
consumer_thread.start()

if __name__ == "__main__":
    app.run(port=8200, host="0.0.0.0")
