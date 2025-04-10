import connexion
import json
import logging.config
import yaml
import os
import time
from flask import jsonify
from threading import Thread, Lock
from pykafka import KafkaClient
from pykafka.common import OffsetType
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

# Kafka setup (Global Client)
hostname = app_config["events"]["hostname"]
port = app_config["events"]["port"]
client = KafkaClient(hosts=f"{hostname}:{port}")
topic = client.topics[app_config["events"]["topic"].encode()]

# Create a message store and counters
messages_store = []  # Only needed if you want to store all messages
counter_lock = Lock()
listings_counter = 0
bids_counter = 0

def get_listings(index): 
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True, 
        consumer_timeout_ms=5000
    )
    counter = 0
    for msg in consumer:
        message = msg.value.decode("utf-8")
        data = json.loads(message)

        if data["type"] == "listings":
            if counter == index:
                logger.info("Found message: listing")
                consumer.stop()  # Make sure to clean up
                return jsonify([data["payload"]]), 200
            counter += 1
    
    consumer.stop()  # Always clean up

    return {"message": f"No message at index {index}!"}, 404


def get_bids(index): 
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True, 
        consumer_timeout_ms=5000
    )   
    counter = 0
    for msg in consumer:
        message = msg.value.decode("utf-8")
        data = json.loads(message)

        if data["type"] == "bids":
            if counter == index:
                logger.info("Found message: bids")
                consumer.stop()  # Make sure to clean up
                return jsonify([data["payload"]]), 200  
            counter += 1
            
    consumer.stop()  # Always clean up

    return {"message": f"No message at index {index}!"}, 404


def get_stats():
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True, 
        consumer_timeout_ms=5000
    )
    listings_counter = 0
    bids_counter = 0

    for msg in consumer:
        data = json.loads(msg.value.decode("utf-8"))
        if data["type"] == "listings":
            listings_counter += 1
        elif data["type"] == "bids":
            bids_counter += 1
            
    consumer.stop()  # Always clean up

    return {"Listings": listings_counter, "Bids": bids_counter}, 200


######################################################################################
def get_listings_ids():
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True, 
        consumer_timeout_ms=5000
    )
    
    result = []
    
    for msg in consumer:
        message = msg.value.decode("utf-8")
        data = json.loads(message)
        
        if data["type"] == "listings":
            payload = data["payload"]
            result.append({
                "event_id": payload["listing_id"],
                "trace_id": payload["trace_id"]
            })
    
    consumer.stop()
    
    logger.info(f"Returning {len(result)} listing IDs from Kafka")
    return result, 200

def get_bids_ids():
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True, 
        consumer_timeout_ms=5000
    )
    
    result = []
    
    for msg in consumer:
        message = msg.value.decode("utf-8")
        data = json.loads(message)
        
        if data["type"] == "bids":
            payload = data["payload"]
            result.append({
                "event_id": payload["bidding_id"],
                "trace_id": payload["trace_id"]
            })
    
    consumer.stop()
    
    logger.info(f"Returning {len(result)} bid IDs from Kafka")
    return result, 200


######################################################################################


# Setup Connexion app
app = connexion.FlaskApp(__name__, specification_dir='')

# Add CORS middleware if enabled via environment variable
if "CORS_ALLOW_ALL" in os.environ and os.environ["CORS_ALLOW_ALL"] == "yes": 
    app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add API with base path for reverse proxy
app.add_api("openapi.yaml", base_path="/analyzer", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    app.run(port=8200, host="0.0.0.0")