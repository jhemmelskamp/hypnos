FROM python:2.7-slim


RUN apt-get update && apt-get install -y git

RUN pip install git+https://github.com/jhemmelskamp/petrarch2.git

ADD . /src

RUN cd /src; pip install -r requirements.txt

EXPOSE 5001

CMD ["python", "/src/petrarch_app.py"]
