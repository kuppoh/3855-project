# you might have to edit dashboard.. or not
# but you might definitely edit the port stuff for nginx

# steps/checklist:
1. create service directory + basic files
2. define the API specification in openapi.yaml
3. create the app_conf.yaml config
4. update log_conf.yaml to add your service
5. implement core functionality in app.py
6. add service to docker-compose.yaml
7. update nginx configuration in dashboard/default.conf
8. update UI components if needed (dashboard/index.html, dashboard/updateStats.js)
9. build and test the service (docker compose up -d --build)

# current port assignments:
8080: Receiver service
8090: Storage service
8100: Processing service
8200: Analyzer service
8300: Consistency Check service
8400-8499: Range for *new* services