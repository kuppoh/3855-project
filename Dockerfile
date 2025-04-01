FROM nginx
COPY dashboard /usr/share/nginx/html
COPY dashboard/default.conf /etc/nginx/conf.d/default.conf