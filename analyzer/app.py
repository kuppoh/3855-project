import connexion, json, logging.config, yaml, os
from flask import jsonify
from datetime import datetime
from pykafka import KafkaClient
from pykafka.common import OffsetType
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

# Kafka setup (Global Consumer)
hostname = app_config["events"]["hostname"]
port = app_config["events"]["port"]
client = KafkaClient(hosts=f"{hostname}:{port}")
topic = client.topics[app_config["events"]["topic"].encode()]

# Flag for manual cleanup control
consumer_active = True
consumer = None


def process_messages():
    global consumer_active, consumer
    logger.info(f"Connecting to Kafka: {hostname}:{port}")
    client = KafkaClient(hosts=f"{hostname}:{port}")
    topic = client.topics[str.encode(app_config['events']['topic'])]

    # Create a consumer with offset reset handling
    consumer = topic.get_simple_consumer(consumer_group=b'event_group', reset_offset_on_start=False, auto_offset_reset=OffsetType.LATEST)

    logger.info("Consumer created. Waiting for messages...")

    while consumer_active:
        try:
            # Blocking, waiting for a new message
            msg = next(consumer)

            msg_str = msg.value.decode('utf-8')
            msg = json.loads(msg_str)
            logger.info("Message: %s" % msg)
            payload = msg["payload"]
            
            if msg["type"] == "listings":
                logger.info("Processing listings event: %s", payload)
                post_listing(payload)
            elif msg["type"] == "bids":
                logger.info("Processing bids event: %s", payload)
                post_bid(payload)

            # Commit the message offset after processing
            consumer.commit_offsets()

        except Exception as e:
            logger.error(f"Error processing message: {e}")
        
        # Check if you want to stop consumer gracefully
        if some_condition_to_stop():
            consumer_active = False

    # Ensure consumer is cleaned up if still active
    if consumer and not consumer.is_closed:
        try:
            logger.info("Cleaning up Kafka consumer...")
            consumer.cleanup()
        except Exception as cleanup_error:
            logger.error(f"Error during consumer cleanup: {cleanup_error}")


# Start the message processing in a background thread
def start_consumer_thread():
    consumer_thread = Thread(target=process_messages)
    consumer_thread.daemon = True
    consumer_thread.start()


# Endpoint functions
def get_listings(index): 
    consumer_local = topic.get_simple_consumer(
        reset_offset_on_start=True, 
        consumer_timeout_ms=5000
    )
    counter = 0
    for msg in consumer_local:
        message = msg.value.decode("utf-8")
        data = json.loads(message)

        if data["type"] == "listings":
            if counter == index:
                logger.info("Found message: listing")
                return jsonify([data["payload"]]), 200
            counter += 1
    
    consumer_local.stop()

    return {"message": f"No message at index {index}!"}, 404


def get_bids(index): 
    consumer_local = topic.get_simple_consumer(
        reset_offset_on_start=True, 
        consumer_timeout_ms=5000
    )   
    counter = 0
    for msg in consumer_local:

        message = msg.value.decode("utf-8")
        data = json.loads(message)

        if data["type"] == "bids":
            if counter == index:
                logger.info("Found message: bids")
                return jsonify([data["payload"]]), 200  
            counter += 1
    consumer_local.stop()

    return {"message": f"No message at index {index}!"}, 404


def get_stats():
    consumer_local = topic.get_simple_consumer(
        reset_offset_on_start=True, 
        consumer_timeout_ms=5000
    )
    listings_counter = 0
    bids_counter = 0

    for msg in consumer_local:

        data = json.loads(msg.value.decode("utf-8"))
        if data["type"] == "listings":
            listings_counter += 1
        elif data["type"] == "bids":
            bids_counter += 1
    consumer_local.stop()

    return {"Listings": listings_counter, "Bids": bids_counter}, 200


# Start the consumer thread
start_consumer_thread()

# Set up the Flask application with CORS if required
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
