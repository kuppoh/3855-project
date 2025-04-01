import connexion, json, logging.config, yaml, pykafka
from flask import jsonify
from connexion import FlaskApp
from pykafka import KafkaClient
import atexit

app = FlaskApp(__name__)

# Middleware setup
app.add_middleware(
    CORSMiddleware,
    position=MiddlewarePosition.BEFORE_EXCEPTION,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration loading
with open('./config/analyzer/app_conf.yaml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open("./config/log_conf.yaml", "r") as f:
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('analyzerLogger')
logger.debug("logging is set up...")

# Kafka client initialization
hostname = app_config["events"]["hostname"]
port = app_config["events"]["port"]
client = KafkaClient(hosts=f"{hostname}:{port}")
topic = client.topics[app_config["events"]["topic"].encode()]

# Initialize the consumer once at the start
consumer = topic.get_simple_consumer(
    reset_offset_on_start=True,
    consumer_timeout_ms=1000,
    consumer_group=b'event_group'
)

# Register consumer cleanup on exit
def cleanup_consumer():
    logger.info("Stopping the Kafka consumer")
    consumer.stop()

atexit.register(cleanup_consumer)

def get_listings(index): 
    counter = 0
    try:
        for msg in consumer:
            message = msg.value.decode("utf-8")
            data = json.loads(message)
            if data["type"] == "listings": 
                if counter == index:
                    logger.info("Found message: listing")
                    return jsonify([data["payload"]]), 200
                counter += 1
    except pykafka.exceptions.ConsumerStoppedException:
        logger.error("Consumer was stopped unexpectedly")
        return {"message": "Consumer was stopped unexpectedly"}, 500

    return {"message": f"No message at index {index}!"}, 404

def get_bids(index): 
    counter = 0
    try:
        for msg in consumer:
            message = msg.value.decode("utf-8")
            data = json.loads(message)
            if data["type"] == "bids": 
                if counter == index:
                    logger.info("Found message: bids")
                    return jsonify([data["payload"]]), 200
                counter += 1
    except pykafka.exceptions.ConsumerStoppedException:
        logger.error("Consumer was stopped unexpectedly")
        return {"message": "Consumer was stopped unexpectedly"}, 500

    return {"message": f"No message at index {index}!"}, 404

def get_stats():
    listings_counter = 0
    bids_counter = 0
    try:
        for msg in consumer:
            data = json.loads(msg.value.decode("utf-8"))
            if data["type"] == "listings":
                listings_counter += 1
            elif data["type"] == "bids":
                bids_counter += 1
    except pykafka.exceptions.ConsumerStoppedException:
        logger.error("Consumer was stopped unexpectedly")
        return {"message": "Consumer was stopped unexpectedly"}, 500

    return {"Listings": listings_counter, "Bids": bids_counter}, 200

# Set up API routes
app.add_api("openapi.yaml", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    app.run(port=8200, host="0.0.0.0")
