# EditorWatch Deployment Checklist

## ✅ Pre-Flight Check

Your project structure is **READY FOR RAILWAY**:

```
editorwatch/                    ← Deploy this entire repo to Railway
├── app.py                      ← ✅ Flask app (Railway entry point)
├── models.py                   ← ✅ Database models
├── requirements.txt            ← ✅ Dependencies (Railway auto-installs)
├── Procfile                    ← ✅ Run commands (Railway auto-reads)
├── runtime.txt                 ← ✅ Python version
├── templates/                  ← ✅ HTML files
│   ├── login.html
│   └── dashboard.html
├── analysis/                   ← ✅ Worker code (imported by app.py)
│   ├── metrics.py
│   ├── visualizer.py
│   └── worker.py
└── extension/                  ← ⚠️  NOT deployed to Railway
    └── ...                         (publish separately to VS Code marketplace)
```

---

## 🚀 Deployment Steps

### Step 1: GitHub (5 min)

```bash
cd editorwatch
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR-USERNAME/editorwatch.git
git push -u origin main
```

✅ Repository is public or accessible to Railway

---

### Step 2: Railway (10 min)

#### A. Create Project
1. Go to [railway.app](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `editorwatch` repository
5. Railway auto-deploys! ✨

**Railway will automatically:**
- Detect Python from `requirements.txt`
- Install dependencies
- Run `gunicorn app:app` from Procfile
- Assign a URL

#### B. Add PostgreSQL
1. In project dashboard, click "+ New"
2. Select "Database" → "PostgreSQL"
3. ✅ `DATABASE_URL` automatically set

#### C. Add Redis
1. Click "+ New" again
2. Select "Database" → "Redis"
3. ✅ `REDIS_URL` automatically set

#### D. Set Environment Variables
Click on your web service → "Variables" tab → Add:

```bash
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
ENCRYPTION_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<choose strong password>
```

#### E. Get Your URL
- Go to "Settings" → "Domains"
- Copy your Railway URL (e.g., `editorwatch-production.up.railway.app`)
- ✅ Backend is live!

---

### Step 3: VS Code Extension (30 min)

#### A. Setup Publisher
1. Go to [marketplace.visualstudio.com/manage](https://marketplace.visualstudio.com/manage)
2. Create publisher account

#### B. Get PAT (Personal Access Token)
1. Go to [dev.azure.com](https://dev.azure.com)
2. User Settings → Personal Access Tokens
3. Create token with "Marketplace (Publish)" scope
4. Save the token!

#### C. Update Extension Config
Edit `extension/package.json`:
```json
{
  "publisher": "YOUR-PUBLISHER-ID",
  "repository": {
    "url": "https://github.com/YOUR-USERNAME/editorwatch"
  }
}
```

#### D. Publish
```bash
npm install -g @vscode/vsce
cd extension
npm install
vsce login YOUR-PUBLISHER-ID  # Enter PAT when prompted
vsce package                   # Test build
vsce publish                   # Publish to marketplace
```

✅ Extension live at: `marketplace.visualstudio.com/items?itemName=YOUR-PUBLISHER.editorwatch`

---

### Step 4: Payment Setup (20 min)

#### Option A: Stripe (Recommended)
1. Create account at [stripe.com](https://stripe.com)
2. Create products:
   - Startup License: $500/year
   - SMB License: $2,500/year
3. Generate payment links
4. Add to LICENSE.md

#### Option B: GitHub Sponsors
1. Enable GitHub Sponsors
2. Create sponsor tiers
3. Add license delivery info

#### Option C: PayPal
1. Get PayPal.me link
2. Add manual license delivery process

---

## 🧪 Testing Checklist

After deployment:

- [ ] Visit Railway URL → See login page
- [ ] Login with admin credentials → See dashboard
- [ ] Create test assignment → Download config
- [ ] Install extension from marketplace
- [ ] Open test folder with `.editorwatch` → Enable monitoring
- [ ] Make some edits → Submit assignment
- [ ] Check dashboard → See submission & metrics

---

## 📊 Cost Summary

| Item | Cost | Notes |
|------|------|-------|
| Railway Hobby | $5/month | Includes PostgreSQL + Redis |
| Domain (optional) | $12/year | If you want custom domain |
| VS Code Marketplace | Free | No cost to publish |
| Stripe | Free | 2.9% + $0.30 per transaction |
| **Total** | **$5-6/month** | Very affordable! |

---

## 🎯 Success Metrics

After 1 week:
- [ ] Backend is accessible 24/7
- [ ] Extension has 10+ installs
- [ ] Created 1-2 test assignments
- [ ] Tested full submission workflow

After 1 month:
- [ ] 50+ extension installs
- [ ] 5+ real instructors using it
- [ ] First commercial license sale

---

## 🆘 Troubleshooting

**Railway deployment failed?**
→ Check logs in Railway dashboard
→ Verify `app.py` is at root
→ Verify `requirements.txt` exists

**Extension won't install?**
→ Wait 10-15 min after publishing
→ Check marketplace status
→ Try `vsce package` locally first

**Can't connect to server?**
→ Check Railway URL is correct
→ Verify environment variables set
→ Check PostgreSQL/Redis are running

---

## 📚 Quick Links

- **Railway Dashboard**: [railway.app/dashboard](https://railway.app/dashboard)
- **VS Code Marketplace**: [marketplace.visualstudio.com/manage](https://marketplace.visualstudio.com/manage)
- **Stripe Dashboard**: [dashboard.stripe.com](https://dashboard.stripe.com)
- **Full Deployment Guide**: See `DEPLOYMENT.md`
- **Railway Help**: See `RAILWAY_DEPLOYMENT.md`

---

**Estimated Total Time: 60-90 minutes**

Good luck! 🚀
