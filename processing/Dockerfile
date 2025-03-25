FROM python:3

LABEL maintainer="kwacnang@my.bcit.ca"

RUN mkdir /app
COPY requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip3 install --upgrade pip && pip3 install setuptools
RUN pip3 install -r requirements.txt 


COPY . /app
RUN mkdir /app/data
RUN mkdir /app/data/processing
RUN echo '{"num_listings": 0, "num_bids": 0, "max_listing_price": 0, "max_offer_price": 0}' > /app/data/processing/data.json


EXPOSE 8100

# Entrypoint = run Python
ENTRYPOINT [ "python3" ]
# Default = run app.py
CMD [ "app.py" ]