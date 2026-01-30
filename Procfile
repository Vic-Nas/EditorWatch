web: cd backend && gunicorn app:app
worker: cd analysis && python -m rq.worker analysis --url $REDIS_URL
