# syntax=docker/dockerfile:1

FROM python:3.9.5

#MAINTANER Your Name "mmahacek@opennms.com"

WORKDIR /app

# We copy just the requirements.txt first to leverage Docker cache
COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY ./src .

ENV FLASK_APP=app

#ENTRYPOINT [ "python" ]

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0", "--port=5000"]
