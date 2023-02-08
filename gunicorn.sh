#!/bin/sh
gunicorn --bind=0.0.0.0:80 --timeout 30 -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 app:app