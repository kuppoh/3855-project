FROM python:3

LABEL maintainer="kwacnang@my.bcit.ca"

RUN mkdir /app

COPY requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip3 install --upgrade pip && pip3 install setuptools
RUN pip3 install -r requirements.txt 

COPY . /app

EXPOSE 8300


ENTRYPOINT [ "python3" ]

CMD [ "app.py" ]
