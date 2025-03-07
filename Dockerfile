FROM python:2.7-slim

RUN apt-get update && apt-get install -y git

ADD . /src

RUN cd /src; pip install -r requirements.txt

EXPOSE 5002

CMD ["python", "/src/app.py"]
