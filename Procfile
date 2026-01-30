web: gunicorn app:app
worker: python -m rq.worker analysis --url $REDIS_URL
