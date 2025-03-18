FROM python:3

LABEL maintainer="kwacnang@my.bcit.ca"

RUN mkdir /app

COPY requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip3 install --upgrade pip && pip3 install setuptools
RUN pip3 install -r requirements.txt 

COPY . /app

# RUN chown -R nobody:nogroup /app
# USER nobody

EXPOSE 8200

# Entrypoint = run Python
ENTRYPOINT [ "python3" ]
# Default = run app.py
CMD [ "app.py" ]