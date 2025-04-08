import connexion, json, datetime, logging.config, yaml, sys
from datetime import datetime
from connexion import NoContent
from database import make_session
from sqlalchemy import select
from models import listings, bids, Base
from confluent_kafka import Consumer, KafkaError  # Updated to use Confluent Kafka
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
    kafka_config = {
        'bootstrap.servers': f"{app_config['events']['hostname']}:{app_config['events']['port']}",
        'group.id': 'event_group',
        'auto.offset.reset': 'latest'
    }

    logger.info(f"Connecting to Kafka: {kafka_config['bootstrap.servers']}.")
    consumer = Consumer(kafka_config)
    consumer.subscribe([app_config['events']['topic']])

    logger.info("Consumer created and subscribed. Waiting for messages...")

    while True:
        msg = consumer.poll(1.0)  # Timeout of 1 second
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                logger.info(f"End of partition reached: {msg.topic()} {msg.partition()}")
            elif msg.error():
                logger.error(f"Error consuming message: {msg.error()}")
            continue

        msg_str = msg.value().decode('utf-8')
        msg = json.loads(msg_str)
        logger.info("Message: %s" % msg)
        payload = msg["payload"]

        if msg["type"] == "listings":
            logger.info("Processing listings event: %s", payload)
            post_listing(payload)
        elif msg["type"] == "bids":
            logger.info("Processing bids event: %s", payload)
            post_bid(payload)

    consumer.close()


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


def setup_kafka_thread():
    logger.info("Setting up Kafka consumer thread")
    t1 = Thread(target=process_messages)
    t1.setDaemon(True)
    t1.start()
    logger.info("Consumer setup done.")


app = connexion.FlaskApp(__name__, specification_dir='')
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
