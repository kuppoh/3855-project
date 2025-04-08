import connexion, json, datetime, httpx, time, yaml, logging.config, os
from connexion import NoContent
from confluent_kafka import Producer

# Load configurations
with open('./config/receiver/app_conf.yaml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open("./config/log_conf.yaml", "r") as f:
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('receiverLogger')

# Kafka setup (Global Producer)
kafka_config = {
    'bootstrap.servers': f"{app_config['events']['hostname']}:{app_config['events']['port']}"
}

producer = Producer(kafka_config)

# Endpoint functions
def post_listing(body):  # post listings
    trace_id = time.time_ns()
    body['trace_id'] = trace_id

    # after generating trace_id, log it immediately
    logger.info(f"Received event: listing-post-event, with a trace_id of: {trace_id}")

    msg = {
        "type": "listings",
        "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "payload": body
    }
    msg_str = json.dumps(msg)

    try:
        producer.produce(app_config['events']['topic'], value=msg_str.encode('utf-8'))
        producer.flush()  # Ensure message is sent before proceeding
        logger.info(f"Response for event: listing-post-event (trace_id: {trace_id})")
        return NoContent, 200
    except Exception as e:
        logger.error(f"Failed to produce message: {e}")
        return {"message": "Failed to send event."}, 500


def post_bid(body):  # post bids/offers
    trace_id = time.time_ns()
    body['trace_id'] = trace_id

    logger.info(f"Received event: bids-post-event, with a trace_id of: {trace_id}")

    msg = {
        "type": "bids",
        "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "payload": body
    }
    msg_str = json.dumps(msg)

    try:
        producer.produce(app_config['events']['topic'], value=msg_str.encode('utf-8'))
        producer.flush()
        logger.info(f"Response for event: bids-post-event (trace_id: {trace_id})")
        return NoContent, 200
    except Exception as e:
        logger.error(f"Failed to produce message: {e}")
        return {"message": "Failed to send event."}, 500


app = connexion.FlaskApp(__name__, specification_dir='')  # look at the current directory for OpenAPI Specifications.
app.add_api("openapi.yaml",  # OpenAPI file to use
            base_path="/receiver",
            strict_validation=True,  # validate reqs + msgs + params for endpoints against API file
            validate_responses=True)  # validate res msgs from endpoints against API file

if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")