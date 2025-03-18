import connexion, json, datetime, httpx, time, yaml, logging.config, pykafka
from connexion import NoContent
from pykafka import KafkaClient



# r = httpx.get('http://storage:8090')

with open('./config/receiver/app_conf.yaml', 'r') as f:
  app_config = yaml.safe_load(f.read())

with open("./config/log_conf.yaml", "r") as f:
  LOG_CONFIG = yaml.safe_load(f.read())
  logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('receiverLogger')

######
client = KafkaClient(hosts=f"{app_config['events']['hostname']}:{app_config['events']['port']}")
topic = client.topics[str.encode(app_config['events']['topic'])]
producer = topic.get_sync_producer()
######

def post_listing(body): # post listings
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
  producer.produce(msg_str.encode('utf-8'))
  # sends HTTP post req to the url, and we get a response

  # as soon as we get a response, log it (r = response)

  logger.info(f"Response for event: listing-post-event (trace_id: {trace_id})")

  return NoContent, 200


def post_bid(body): # post bids/offers
  trace_id = time.time_ns()
  body['trace_id'] = trace_id

  logger.info(f"Received event: bids-post-event, with a trace_id of: {trace_id}")

  msg = { 
    "type": "bids",
    "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "payload": body
  }
  msg_str = json.dumps(msg)
  producer.produce(msg_str.encode('utf-8'))

  logger.info(f"Response for event: bids-post-event (trace_id: {trace_id})")

  return NoContent, 200

app = connexion.FlaskApp(__name__, specification_dir='') # look at the current directory for OpenAPI Specifications.
app.add_api("openapi.yaml", # OpenAPI file to use
  strict_validation=True, # validate reqs + msgs + params for endpoints against API file
  validate_responses=True) # validate res msgs from endpoints against API file

if __name__ == "__main__":
  app.run(port=8080, host="0.0.0.0")