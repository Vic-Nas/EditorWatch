# Railway Deployment - Quick Reference

## Project Structure for Railway

The project is **already configured** for Railway deployment:

✅ **Root-level files (Railway looks here):**
- `app.py` - Flask application entry point
- `models.py` - Database models  
- `requirements.txt` - All Python dependencies
- `Procfile` - Tells Railway how to run your app
- `runtime.txt` - Specifies Python 3.11
- `templates/` - Flask HTML templates

✅ **Subdirectories:**
- `analysis/` - Worker code (imported by app.py)
- `extension/` - VS Code extension (NOT deployed to Railway - publish separately)

## Railway Auto-Detection

When you connect your GitHub repo to Railway, it will:

1. ✅ Auto-detect Python project (from `requirements.txt` at root)
2. ✅ Read `Procfile` to know how to run your app
3. ✅ Install dependencies from `requirements.txt`
4. ✅ Run `gunicorn app:app` (from Procfile)

## You Don't Need To:

- ❌ Select a specific directory (app.py is at root)
- ❌ Configure build settings (Procfile handles it)
- ❌ Set Python version manually (runtime.txt handles it)

## You DO Need To:

1. ✅ Add PostgreSQL database service (in Railway dashboard)
2. ✅ Add Redis service (in Railway dashboard)
3. ✅ Set environment variables:
   - `SECRET_KEY`
   - `ENCRYPTION_KEY`
   - `ADMIN_USERNAME`
   - `ADMIN_PASSWORD`

Railway automatically sets `DATABASE_URL`, `REDIS_URL`, and `PORT`.

## Deployment Process

```bash
# 1. Push to GitHub
git init
git add .
git commit -m "Deploy EditorWatch"
git push origin main

# 2. In Railway:
# - New Project → Deploy from GitHub
# - Select editorwatch repo
# - Railway deploys automatically from root!
# - Add PostgreSQL + Redis services
# - Set environment variables
# - Done!
```

## Verification

After deployment:
1. Check Railway logs for "Running on..."
2. Visit your Railway URL
3. Should see login page
4. Login with your admin credentials

## Common Issues

**Problem:** "No module named 'app'"
**Solution:** Check that app.py is at root level (not in subdirectory)

**Problem:** Database connection error
**Solution:** Make sure PostgreSQL service is added and DATABASE_URL exists

**Problem:** Worker not processing jobs
**Solution:** Make sure Redis service is added and worker is running (check Procfile)

---

**TL;DR:** Just push to GitHub, connect to Railway, add databases, set env vars. Railway handles the rest! 🚀
