import connexion, json, datetime, logging.config, yaml, sys, os
from datetime import datetime
from connexion import NoContent
from database import make_session
from sqlalchemy import select
from models import listings, bids, Base
from pykafka import KafkaClient
from pykafka.common import OffsetType
from threading import Thread
from commands import create_tables, drop_tables
from database import engine

with open('./config/storage/app_conf.yaml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open("./config/log_conf.yaml", "r") as f:
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('storageLogger')


def process_messages():
    """Process messages from Kafka"""
    # Connect to Kafka
    logger.info(f"Connecting to Kafka: {app_config['events']['hostname']}:{app_config['events']['port']}")
    client = KafkaClient(hosts=f"{app_config['events']['hostname']}:{app_config['events']['port']}")
    topic = client.topics[app_config['events']['topic'].encode()]
    
    # Create a consumer that starts from the earliest offset and doesn't commit offsets
    consumer = topic.get_simple_consumer(
        consumer_group=b'event_group',
        reset_offset_on_start=False,
        auto_offset_reset=OffsetType.LATEST
    )
    
    logger.info("Consumer created and subscribed. Waiting for messages...")
    
    # Process messages
    for msg in consumer:
        if msg is not None:
            try:
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
                    
                # Commit the offset after processing
                consumer.commit_offsets()
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")


def post_listing(body):
    obj = listings(
        listing_id=body["listing_id"],
        listing_price=body["listing_price"],
        listing_type=body["listing_type"],
        listing_status=body["listing_status"],
        listing_contact=body["listing_contact"],
        trace_id=body["trace_id"])

    logger.debug(f"Stored event: listing-post-event, with trace_id: {obj.trace_id}")

    session = make_session()
    session.add(obj)
    session.commit()
    session.close()

    return NoContent, 201


def post_bid(body):
    obj = bids(
        bidding_id=body["bidding_id"],
        listing_id=body["listing_id"],
        asking_price=body["asking_price"],
        offer_price=body["offer_price"],
        property_square_feet=body["property_square_feet"],
        price_per_square_feet=body["price_per_square_feet"],
        bid_status=body["bid_status"],
        trace_id=body["trace_id"])

    logger.debug(f"Stored event: bids-post-event, with trace_id: {obj.trace_id}")

    session = make_session()
    session.add(obj)
    session.commit()
    session.close()

    return NoContent, 201


def get_listings(start_timestamp, end_timestamp):
    session = make_session()

    start = datetime.strptime(start_timestamp, "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(end_timestamp, "%Y-%m-%d %H:%M:%S")

    statement = select(listings).where(listings.listing_post >= start).where(listings.listing_post < end)

    result = [
        {
            "listing_id": row.listing_id,
            "listing_price": row.listing_price,
            "listing_post": row.listing_post,
            "listing_type": row.listing_type,
            "listing_status": row.listing_status.value,
            "listing_contact": row.listing_contact,
            "trace_id": row.trace_id
        }
        for row in session.execute(statement).scalars().all()
    ]

    session.close()

    logger.info("Found %d listings (start: %s | end: %s)", len(result), start, end)
    return result


def get_bids(start_timestamp, end_timestamp):
    session = make_session()

    start = datetime.strptime(start_timestamp, "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(end_timestamp, "%Y-%m-%d %H:%M:%S")

    statement = select(bids).where(bids.offer_date >= start).where(bids.offer_date < end)

    result = [
        {
            "bidding_id": row.bidding_id,
            "listing_id": row.listing_id,
            "asking_price": row.asking_price,
            "offer_price": row.offer_price,
            "offer_date": row.offer_date,
            "property_square_feet": row.property_square_feet,
            "price_per_square_feet": row.price_per_square_feet,
            "bid_status": row.bid_status.value,
            "trace_id": row.trace_id
        }
        for row in session.execute(statement).scalars().all()
    ]

    session.close()

    logger.info("Found %d bids (start: %s | end: %s)", len(result), start, end)
    return result

#########################################################################################
def get_all_events_count():
    session = make_session()
    
    # Count all listings and bids
    listing_count = session.query(listings).count()
    bid_count = session.query(bids).count()
    
    result = {
        "listings": listing_count,
        "bids": bid_count
    }
    
    session.close()
    
    logger.info(f"Returning counts - listings: {listing_count}, bids: {bid_count}")
    return result, 200

def get_listings_ids():
    session = make_session()
    
    # Get all listings IDs and trace IDs
    result = [
        {
            "event_id": row.listing_id,
            "trace_id": row.trace_id
        }
        for row in session.query(listings).all()
    ]
    
    session.close()
    
    logger.info(f"Returning {len(result)} listing IDs")
    return result, 200

def get_bids_ids():
    session = make_session()
    
    # Get all bid IDs and trace IDs
    result = [
        {
            "event_id": row.bidding_id,
            "trace_id": row.trace_id
        }
        for row in session.query(bids).all()
    ]
    
    session.close()
    
    logger.info(f"Returning {len(result)} bid IDs")
    return result, 200

#########################################################################################


def setup_kafka_thread():
    """Set up a background thread to consume messages from Kafka"""
    logger.info("Setting up Kafka consumer thread")
    t1 = Thread(target=process_messages)
    t1.daemon = True
    t1.start()
    logger.info("Consumer setup done.")


app = connexion.FlaskApp(__name__, specification_dir='')

# Add CORS middleware if enabled via environment variable
if "CORS_ALLOW_ALL" in os.environ and os.environ["CORS_ALLOW_ALL"] == "yes":
    from starlette.middleware.cors import CORSMiddleware
    from connexion.middleware import MiddlewarePosition
    
    app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_api("openapi.yaml",
            base_path="/storage",
            strict_validation=True,
            validate_responses=True)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        logger.info("Dropping tables...")
        drop_tables()

        logger.info("Creating tables for reset...")
        create_tables()
    else:
        logger.info("Creating tables...")
        create_tables()

    setup_kafka_thread()
    app.run(port=8090, host="0.0.0.0")