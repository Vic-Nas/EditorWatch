# EditorWatch Deployment Guide

This guide covers deploying EditorWatch to production.

## Prerequisites

- Python 3.11+
- PostgreSQL database
- Redis instance
- (Optional) SMTP server for email

## Environment Variables

Required:
```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname
REDIS_URL=redis://host:6379
SECRET_KEY=<random-32-char-string>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<secure-password>
ENCRYPTION_KEY=<fernet-key>  # Optional - auto-generates if missing
```

Optional (SMTP):
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
SERVER_URL=https://your-domain.com  # Optional - auto-detects
```

## Railway Deployment (Easiest)

1. **Create Railway Project**:
   - Go to [railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your EditorWatch fork

2. **Add PostgreSQL**:
   - Click "New" → "Database" → "PostgreSQL"
   - Railway auto-sets `DATABASE_URL`

3. **Add Redis**:
   - Click "New" → "Database" → "Redis"
   - Railway auto-sets `REDIS_URL`

4. **Set Variables**:
   - Go to your web service → Variables
   - Add: `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`
   - Add SMTP vars if you want email support

5. **Deploy**:
   - Railway auto-detects `Procfile`
   - Runs `web: gunicorn app:app`
   - Runs `worker: python -m rq.worker analysis --url $REDIS_URL`
   - Both processes start automatically

6. **Done!** Your app is live at `https://yourapp.railway.app`

## Heroku Deployment

```bash
# Install Heroku CLI
brew install heroku/brew/heroku

# Login
heroku login

# Create app
heroku create your-app-name

# Add addons
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:mini

# Set config
heroku config:set SECRET_KEY=$(openssl rand -hex 32)
heroku config:set ADMIN_USERNAME=admin
heroku config:set ADMIN_PASSWORD=your-password

# Deploy
git push heroku main

# Scale worker
heroku ps:scale worker=1
```

## DigitalOcean/VPS Deployment

### 1. Server Setup

```bash
# SSH into server
ssh root@your-server-ip

# Install dependencies
apt update
apt install -y python3.11 python3-pip postgresql redis-server nginx supervisor

# Create user
adduser editorwatch
usermod -aG sudo editorwatch
su - editorwatch
```

### 2. App Setup

```bash
# Clone repo
git clone https://github.com/Vic-Nas/EditorWatch
cd EditorWatch

# Create virtual env
python3.11 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 3. Database Setup

```bash
# Create PostgreSQL database
sudo -u postgres psql
CREATE DATABASE editorwatch;
CREATE USER editorwatch_user WITH PASSWORD 'secure-password';
GRANT ALL PRIVILEGES ON DATABASE editorwatch TO editorwatch_user;
\q
```

### 4. Environment Setup

```bash
# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://editorwatch_user:secure-password@localhost/editorwatch
REDIS_URL=redis://localhost:6379
SECRET_KEY=$(openssl rand -hex 32)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-password
EOF

# Load environment
export $(cat .env | xargs)
```

### 5. Initialize Database

```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### 6. Supervisor Config (Process Manager)

```bash
sudo nano /etc/supervisor/conf.d/editorwatch.conf
```

Add:
```ini
[program:editorwatch_web]
command=/home/editorwatch/EditorWatch/venv/bin/gunicorn app:app --bind 127.0.0.1:5000 --workers 4
directory=/home/editorwatch/EditorWatch
user=editorwatch
autostart=true
autorestart=true
environment=DATABASE_URL="postgresql://editorwatch_user:secure-password@localhost/editorwatch",REDIS_URL="redis://localhost:6379",SECRET_KEY="your-secret-key",ADMIN_USERNAME="admin",ADMIN_PASSWORD="your-password"

[program:editorwatch_worker]
command=/home/editorwatch/EditorWatch/venv/bin/python -m rq.worker analysis --url redis://localhost:6379
directory=/home/editorwatch/EditorWatch
user=editorwatch
autostart=true
autorestart=true
environment=DATABASE_URL="postgresql://editorwatch_user:secure-password@localhost/editorwatch",REDIS_URL="redis://localhost:6379",SECRET_KEY="your-secret-key"
```

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

### 7. Nginx Config (Reverse Proxy)

```bash
sudo nano /etc/nginx/sites-available/editorwatch
```

Add:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/editorwatch /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 8. SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Docker Deployment

```bash
# Build image
docker build -t editorwatch .

# Run with docker-compose
docker-compose up -d
```

Example `docker-compose.yml`:
```yaml
version: '3.8'
services:
  web:
    build: .
    command: gunicorn app:app --bind 0.0.0.0:5000
    ports:
      - "5000:5000"
    environment:
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