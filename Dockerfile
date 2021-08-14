FROM python:3.7

WORKDIR /tlmhl

ENV FLASK_APP=run.py

RUN apt-get install gcc

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

EXPOSE 5000
COPY . .
CMD ["flask", "run"]
