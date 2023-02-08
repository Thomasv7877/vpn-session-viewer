FROM python:alpine

COPY requirements.txt /
RUN pip install -r /requirements.txt

COPY audit_export /audit_export
COPY . /app
WORKDIR /app

ENTRYPOINT ["./gunicorn.sh"]