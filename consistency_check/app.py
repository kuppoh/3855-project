import connexion
import json
import logging.config
import yaml
import os
import time
import datetime
import httpx
from connexion import NoContent
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware

# Load configurations
with open('./config/consistency_check/app_conf.yaml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open('./config/log_conf.yaml', 'r') as f:
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('consistencyLogger')

# Define the datastore file path
DATASTORE_FILE = app_config['datastore']['filename']

def update_checks():
  """Update consistency checks by querying services and comparing data"""
  start_time = time.time()
  
  logger.info("Starting consistency checks update process")
  
  # Initialize result structure
  result = {
      "last_updated": datetime.datetime.now().isoformat(),
      "counts": {
          "db": {
              "listings": 0,
              "bids": 0
          },
          "queue": {
              "listings": 0,
              "bids": 0
          },
          "processing": {
              "listings": 0,
              "bids": 0
          }
      },
      "missing_in_db": [],
      "missing_in_queue": []
  }
  
  # Get processing stats
  try:
      processing_response = httpx.get(f"{app_config['services']['processing']['url']}/stats")
      if processing_response.status_code == 200:
          processing_data = processing_response.json()
          result["counts"]["processing"]["listings"] = processing_data.get("num_listings", 0)
          result["counts"]["processing"]["bids"] = processing_data.get("num_bids", 0)
      else:
          logger.error(f"Failed to get processing stats: {processing_response.status_code}")
  except Exception as e:
      logger.error(f"Exception when calling processing service: {str(e)}")
  
  # Get storage counts
  try:
      listings_count_response = httpx.get(f"{app_config['services']['storage']['url']}/site/listings/count")
      if listings_count_response.status_code == 200:
          result["counts"]["db"]["listings"] = listings_count_response.json().get("count_listings", 0)
      else:
          logger.error(f"Failed to get listings count from storage: {listings_count_response.status_code}")
          
      bids_count_response = httpx.get(f"{app_config['services']['storage']['url']}/site/bids/count")
      if bids_count_response.status_code == 200:
          result["counts"]["db"]["bids"] = bids_count_response.json().get("count_bids", 0)
      else:
          logger.error(f"Failed to get bids count from storage: {bids_count_response.status_code}")
  except Exception as e:
      logger.error(f"Exception when calling storage service for counts: {str(e)}")
  
  # Get analyzer counts
  try:
      analyzer_stats_response = httpx.get(f"{app_config['services']['analyzer']['url']}/stats")
      if analyzer_stats_response.status_code == 200:
          analyzer_data = analyzer_stats_response.json()
          result["counts"]["queue"]["listings"] = analyzer_data.get("Listings", 0)
          result["counts"]["queue"]["bids"] = analyzer_data.get("Bids", 0)
      else:
          logger.error(f"Failed to get analyzer stats: {analyzer_stats_response.status_code}")
  except Exception as e:
      logger.error(f"Exception when calling analyzer service for stats: {str(e)}")
  
  # Get storage IDs
  db_listings_ids = {}
  db_bids_ids = {}
  
  try:
      listings_ids_response = httpx.get(f"{app_config['services']['storage']['url']}/site/listings/ids")
      if listings_ids_response.status_code == 200:
          for item in listings_ids_response.json():
              db_listings_ids[str(item["trace_id"])] = item["event_id"]
      else:
          logger.error(f"Failed to get listings IDs from storage: {listings_ids_response.status_code}")
          
      bids_ids_response = httpx.get(f"{app_config['services']['storage']['url']}/site/bids/ids")
      if bids_ids_response.status_code == 200:
          for item in bids_ids_response.json():
              db_bids_ids[str(item["trace_id"])] = item["event_id"]
      else:
          logger.error(f"Failed to get bids IDs from storage: {bids_ids_response.status_code}")
  except Exception as e:
      logger.error(f"Exception when calling storage service for IDs: {str(e)}")
  
  # Get analyzer IDs
  queue_listings_ids = {}
  queue_bids_ids = {}
  
  try:
      queue_listings_ids_response = httpx.get(f"{app_config['services']['analyzer']['url']}/site/listings/ids")
      if queue_listings_ids_response.status_code == 200:
          for item in queue_listings_ids_response.json():
              queue_listings_ids[str(item["trace_id"])] = item["event_id"]
      else:
          logger.error(f"Failed to get listings IDs from analyzer: {queue_listings_ids_response.status_code}")
          
      queue_bids_ids_response = httpx.get(f"{app_config['services']['analyzer']['url']}/site/bids/ids")
      if queue_bids_ids_response.status_code == 200:
          for item in queue_bids_ids_response.json():
              queue_bids_ids[str(item["trace_id"])] = item["event_id"]
      else:
          logger.error(f"Failed to get bids IDs from analyzer: {queue_bids_ids_response.status_code}")
  except Exception as e:
      logger.error(f"Exception when calling analyzer service for IDs: {str(e)}")
  
  # Compare listings IDs to find missing in DB
  for trace_id, event_id in queue_listings_ids.items():
      if trace_id not in db_listings_ids:
          result["missing_in_db"].append({
              "event_id": event_id,
              "trace_id": trace_id,
              "type": "listings"
          })
  
  # Compare bids IDs to find missing in DB
  for trace_id, event_id in queue_bids_ids.items():
      if trace_id not in db_bids_ids:
          result["missing_in_db"].append({
              "event_id": event_id,
              "trace_id": trace_id,
              "type": "bids"
          })
  
  # Compare listings IDs to find missing in queue
  for trace_id, event_id in db_listings_ids.items():
      if trace_id not in queue_listings_ids:
          result["missing_in_queue"].append({
              "event_id": event_id,
              "trace_id": trace_id,
              "type": "listings"
          })
  
  # Compare bids IDs to find missing in queue
  for trace_id, event_id in db_bids_ids.items():
      if trace_id not in queue_bids_ids:
          result["missing_in_queue"].append({
              "event_id": event_id,
              "trace_id": trace_id,
              "type": "bids"
          })
  
  # Calculate processing time
  end_time = time.time()
  processing_time_ms = int((end_time - start_time) * 1000)
  
  # Save result to file
  try:
      # Ensure directory exists
      os.makedirs(os.path.dirname(DATASTORE_FILE), exist_ok=True)
      
      with open(DATASTORE_FILE, 'w') as f:
          json.dump(result, f, indent=2)
  except Exception as e:
      logger.error(f"Error saving consistency check results: {str(e)}")
  
  # Log completion
  missing_in_db_count = len(result["missing_in_db"])
  missing_in_queue_count = len(result["missing_in_queue"])
  
  logger.info(f"Consistency checks completed | processing_time_ms={processing_time_ms} | missing_in_db={missing_in_db_count} | missing_in_queue={missing_in_queue_count}")
  
  return {"processing_time_ms": processing_time_ms}, 200

def get_checks():
  """Get the results of the latest consistency check"""
  if not os.path.exists(DATASTORE_FILE):
      return {"message": "No consistency checks have been run yet"}, 404
  
  try:
      with open(DATASTORE_FILE, 'r') as f:
          return json.load(f), 200
  except Exception as e:
      logger.error(f"Error reading consistency check results: {str(e)}")
      return {"message": f"Error reading consistency check results: {str(e)}"}, 500

# Create the Connexion app
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
app.add_api("openapi.yaml", 
  base_path="/consistency_check", 
  strict_validation=True, 
  validate_responses=True)

if __name__ == "__main__":
    app.run(port=app_config["server"]["port"], host="0.0.0.0")