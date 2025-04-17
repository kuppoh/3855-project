import connexion, json, datetime, logging.config, yaml, sys, os
from datetime import datetime
from connexion import NoContent
from sqlalchemy import select
from pykafka import KafkaClient
from pykafka.common import OffsetType
from threading import Thread
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware



with open('./config/anomaly_detector/app_conf.yaml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open("./config/log_conf.yaml", "r") as f:
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('anomalyLogger')

DATASTORE = app_config['datastore']['filename']

hostname = app_config["events"]["hostname"]
port = app_config["events"]["port"]
client = KafkaClient(hosts=f"{hostname}:{port}")
topic = client.topics[app_config["events"]["topic"].encode()]


LISTING_PRICE_THRESHOLD = os.environ["LISTING_PRICE_THRESHOLD"]

def update_anomalies():

    result = {
        "listing_anomalies": [],
        "bid_anomalies": []
    }
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True, 
        consumer_timeout_ms=5000
    )

    for msg in consumer: 
        message = msg.value.decode("utf-8")
        data = json.loads(message)

        if data["type"] == "listings":
            if data["listing_price"] < LISTING_PRICE_THRESHOLD:
                result["listing_anomalies"].append({
                    "event_type": "listings",
                    "event_id": data["event_id"],
                    "trace_id": data["trace_id"],
                    "description": f"Given value: {data["listing_price"]}, threshold: ${LISTING_PRICE_THRESHOLD}"
                }

                )

        if data["type"] == "bids":
            if data["offer_price"] < data["asking_price"]:
                result["bid_anomalies"].append({
                    "event_type": "bids",
                    "event_id": data["event_id"],
                    "trace_id": data["trace_id"],
                    "description": f"Given value: {data["offer_price"]}, is lower than the asking price: {data["asking_price"]}."
                }

                ) 

    with open(DATASTORE, 'w') as f:
        json.dump(result, f, indent=2)

    consumer.stop()
    
    return {"message": f"Finished updates"}, 200


DEFAULT_VAL = {
    "listing_anomalies": [],
    "bid_anomalies": []
}


def get_anomalies(event_type=None):
    if event_type == "listings":
        with open(DATASTORE, 'r') as f:
            return json.load(f["listing_anomalies"]), 200
    elif event_type == "bids":
        with open(DATASTORE, 'r') as f:
            return json.load(f["bid_anomalies"]), 200
    elif event_type == None:
        with open(DATASTORE, 'r') as f:
            if length(f) < 2:
                return DEFAULT_VAL, 200
            else:
                return json.load(f), 200
    else:
        return f"event type provided is invalid.", 404


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


app.add_api("openapi.yaml", 
    base_path="/anomaly_detector", 
    strict_validation=True, 
    validate_responses=True)

if __name__ == "__main__":
    app.run(port=app_config["server"]["port"], host="0.0.0.0")