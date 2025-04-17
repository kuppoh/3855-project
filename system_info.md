## System Overview

This is a microservices-based application with several components:

1. **Receiver Service** - Accepts API requests and publishes to Kafka
2. **Storage Service** - Consumes from Kafka and stores in MySQL database
3. **Analyzer Service** - Reads events from Kafka for analysis
4. **Processing Service** - Processes data and generates statistics
5. **Consistency Check Service** - Verifies data consistency across services
6. **Dashboard** - Provides a frontend UI for monitoring the system

The application manages real estate listings and bids on properties.

## Communication Flow

When a new listing or bid is posted, here's what happens:

1. **Initial Request**: A client sends an HTTP POST to the Receiver service.
2. **Kafka Publication**: Receiver adds a trace_id to the request and publishes it to a Kafka topic.
3. **Event Storage**: The Storage service consumes from Kafka and persists the event to a MySQL database.
4. **Event Analysis**: The Analyzer service reads events from Kafka for analytics purposes.
5. **Data Processing**: The Processing service periodically requests data from Storage and computes statistics.
6. **Consistency Checks**: The Consistency Check service verifies data integrity across microservices.

## Detailed Component Explanation

### 1. Receiver Service (Port 8080)
- Accepts HTTP POST requests for listings and bids
- Assigns a trace_id (timestamp-based) for tracking
- Publishes events to Kafka
- Acts as the entry point for data

```python
# From receiver/app.py
def post_listing(body):  
    trace_id = time.time_ns()
    body['trace_id'] = trace_id
    
    # Publish to Kafka
    msg = {
        "type": "listings",
        "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "payload": body
    }
    producer.produce(json.dumps(msg).encode('utf-8'))
```

### 2. Storage Service (Port 8090)
- Consumes events from Kafka
- Persists data to MySQL database
- Provides GET endpoints for retrieving historical data

```python
# From storage/app.py
def process_messages():
    for msg in consumer:
        if msg is not None:
            msg_str = msg.value.decode('utf-8')
            msg = json.loads(msg_str)
            payload = msg["payload"]
            
            if msg["type"] == "listings":
                post_listing(payload)
            elif msg["type"] == "bids":
                post_bid(payload)
```

### 3. Analyzer Service (Port 8200)
- Reads events from Kafka
- Provides endpoints to query Kafka event data
- Acts as a read-only service for event analysis

```python
# From analyzer/app.py
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
                return jsonify([data["payload"]]), 200
            counter += 1
```

### 4. Processing Service (Port 8100)
- Periodically retrieves data from Storage service
- Computes statistics (counts, maximums)
- Stores processed stats in a JSON file
- Provides GET endpoint for statistics

```python
# From processing/app.py
def populate_stats():
    # Get events within time range from Storage
    params = {'start_timestamp': last_updated, 'end_timestamp': curr_date}
    r1 = httpx.get(app_config['eventstores']['site_listings']['url'], params=params)
    r2 = httpx.get(app_config['eventstores']['site_bids']['url'], params=params)
    
    # Calculate statistics
    num_listings = len(r1.json())
    num_bids = len(r2.json())
    
    # Update and store statistics
    updated_data = {
        "num_listings": data['num_listings'] + num_listings,
        "num_bids": data['num_bids'] + num_bids,
        "max_listing_price": max_listing_price,
        "max_offer_price": max_offer_price,
        "last_updated": curr_date
    }
```

### 5. Consistency Check Service (Port 8300)
- Compares data between Kafka and database
- Identifies missing or inconsistent events
- Helps ensure data integrity across the system

```python
# From consistency_check/app.py
def update_checks():
    # Get counts from various services
    processing_response = httpx.get(f"{app_config['services']['processing']['url']}/stats")
    events_count_response = httpx.get(f"{app_config['services']['storage']['url']}/site/events/count")
    analyzer_stats_response = httpx.get(f"{app_config['services']['analyzer']['url']}/stats")
    
    # Compare IDs between services to find inconsistencies
    for trace_id, event_id in queue_listings_ids.items():
        if trace_id not in db_listings_ids:
            result["missing_in_db"].append({
                "event_id": event_id,
                "trace_id": trace_id,
                "type": "listings"
            })
```

### 6. Dashboard (Port 80 via Nginx)
- Web UI that displays system statistics and status
- Makes AJAX requests to the backend services
- Provides visualizations of the system's state

The Nginx configuration routes requests to appropriate backend services:

```
location /receiver {
    proxy_pass http://receiver:8080;
}

location /analyzer {
    proxy_pass http://analyzer:8200;
}
```

## Data Flow Example

1. A user submits a new property listing via HTTP POST to `/receiver/site/listings`
2. The Receiver service assigns a trace_id and publishes the event to Kafka
3. Storage service consumes this event and saves it to MySQL
4. Analyzer service can retrieve this event for analytics
5. Processing service periodically pulls data from Storage, including this listing
6. Processing updates statistics like total listings count and max price
7. Consistency Check service verifies this listing exists in both Kafka and MySQL
8. Dashboard queries these services to display updated statistics

## Key Technologies

- **Kafka**: Message queue for event sourcing and decoupling
- **MySQL**: Persistent storage for listings and bids
- **Docker & Docker Compose**: Container orchestration
- **Flask/Connexion**: API frameworks for microservices
- **Nginx**: Reverse proxy and static content server

This architecture follows microservices best practices with:
- Service independence
- Asynchronous communication
- Event sourcing
- Data consistency checking
- Containerized deployment