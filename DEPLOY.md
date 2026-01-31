# EditorWatch Deployment (short)

This file contains minimal deployment guidance. For full usage see `README.md` and use `.env.example` as a template for required environment variables.

Quick steps:

1. Create a server (or use Railway/Heroku). Ensure `DATABASE_URL` and `REDIS_URL` are available.
2. Copy `.env.example` to `.env` and set `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and optionally `ENCRYPTION_KEY` and `SMTP_*`.
3. Install requirements and initialize the database:

```bash
pip install -r requirements.txt
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

4. Start processes (example using gunicorn + RQ worker):

```bash
gunicorn app:app --bind 0.0.0.0:5000
python -m rq.worker analysis --url $REDIS_URL
```

That's it — for advanced setups (nginx, supervisor, docker, CI) refer to `README.md`.
      - DATABASE_URL=postgresql://postgres:password@db:5432/editorwatch
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=your-secret-key
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=password
    depends_on:
      - db
      - redis
  
  worker:
    build: .
    command: python -m rq.worker analysis --url redis://redis:6379
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/editorwatch
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=your-secret-key
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=editorwatch
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine

volumes:
  postgres_data:
```

## Troubleshooting

### Worker not processing jobs
```bash
# Check Redis connection
redis-cli ping

# Check RQ status
python -c "from redis import Redis; from rq import Queue; r = Redis.from_url('redis://localhost:6379'); q = Queue('analysis', connection=r); print(f'Jobs: {len(q)}')"

# Restart worker
supervisorctl restart editorwatch_worker
```

### Database connection errors
```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check if tables exist
python -c "from app import app, db; app.app_context().push(); print(db.engine.table_names())"
```

### SMTP not sending emails
- Check firewall allows port 587
- Use app-specific password for Gmail
- Verify SMTP credentials
- Check logs for specific error

### Extension can't connect
- Verify SERVER_URL is correct (must be HTTPS for Railway)
- Check firewall allows incoming connections
- Test API: `curl https://your-server.com/api/assignments`

## Monitoring

### Logs
```bash
# Web logs
supervisorctl tail -f editorwatch_web

# Worker logs
supervisorctl tail -f editorwatch_worker

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Health Checks
```bash
# Web server
curl https://your-domain.com/

# Database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM submissions"

# Redis
redis-cli ping
```

## Backups

### Database
```bash
# Backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Restore
psql $DATABASE_URL < backup.sql
```

### Automated Backups (cron)
```bash
crontab -e

# Add daily backup at 2am
0 2 * * * pg_dump postgresql://user:pass@localhost/editorwatch > /backups/editorwatch_$(date +\%Y\%m\%d).sql
```

## Security Checklist

- [ ] Change default admin password
- [ ] Use strong SECRET_KEY (32+ random chars)
- [ ] Enable HTTPS (Let's Encrypt)
- [ ] Set up firewall (only ports 80, 443, 22)
- [ ] Regular database backups
- [ ] Keep dependencies updated
- [ ] Monitor logs for suspicious activity
- [ ] Rotate ENCRYPTION_KEY periodically

## Scaling

For 1000+ students:

1. **Increase workers**: `supervisorctl scale editorwatch_worker=3`
2. **Add more Gunicorn workers**: `--workers 8`
3. **Upgrade database**: More RAM/CPU
4. **Use Redis persistence**: Edit redis.conf to enable AOF
5. **Add load balancer**: Nginx upstream for multiple app servers

## Updates

```bash
cd EditorWatch
git pull origin main
pip install -r requirements.txt
supervisorctl restart all
```