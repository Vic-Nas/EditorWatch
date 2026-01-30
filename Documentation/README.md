# EditorWatch - Complete Setup Guide

## Project Structure

```
editorwatch/
├── extension/          # VS Code extension
│   ├── package.json
│   ├── extension.js
│   └── .vscodeignore
├── backend/           # Flask API server
│   ├── app.py
│   ├── models.py
│   ├── requirements.txt
│   └── templates/
├── analysis/          # Metrics & visualization
│   ├── metrics.py
│   ├── visualizer.py
│   └── worker.py
├── Procfile          # Railway deployment
└── railway.json      # Railway config
```

## Quick Start

### 1. Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
export DATABASE_URL="sqlite:///editorwatch.db"
export SECRET_KEY="your-secret-key"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="changeme"
python app.py
```

**Extension Development:**
```bash
cd extension
npm install
# Open in VS Code
# Press F5 to launch extension development host
```

### 2. Deploy to Railway

**Prerequisites:**
- GitHub account
- Railway account (railway.app)

**Steps:**

1. **Push to GitHub:**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/editorwatch.git
git push -u origin main
```

2. **Deploy on Railway:**
   - Go to railway.app
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `editorwatch` repository
   - Railway auto-detects Python and deploys

3. **Add Services:**
   - Click "New" → "Database" → "PostgreSQL"
   - Click "New" → "Database" → "Redis"
   - Railway automatically sets `DATABASE_URL` and `REDIS_URL`

4. **Set Environment Variables:**
   In Railway dashboard, add:
   - `SECRET_KEY`: Generate with `python -c "import secrets; print(secrets.token_hex(32))"`
   - `ENCRYPTION_KEY`: Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `ADMIN_USERNAME`: Your admin username
   - `ADMIN_PASSWORD`: Your admin password

5. **Get Your URL:**
   Railway generates: `https://editorwatch-production.up.railway.app`

### 3. Publish Extension to VS Code Marketplace

**Prerequisites:**
- VS Code installed
- `vsce` CLI tool: `npm install -g @vscode/vsce`
- Azure DevOps account for Personal Access Token

**Steps:**

1. **Create Publisher Account:**
   - Go to marketplace.visualstudio.com/manage
   - Create a publisher (e.g., "yourname")

2. **Get Personal Access Token (PAT):**
   - Go to dev.azure.com
   - User Settings → Personal Access Tokens
   - Create new token with "Marketplace (Publish)" scope
   - Save the token

3. **Update package.json:**
```bash
cd extension
# Edit package.json - change "publisher" to your publisher name
```

4. **Package and Publish:**
```bash
vsce login yourpublishername
# Enter your PAT when prompted

vsce package
# Creates editorwatch-0.1.0.vsix

vsce publish
# Publishes to marketplace
```

5. **Extension URL:**
   `https://marketplace.visualstudio.com/items?itemName=yourpublisher.editorwatch`

### 4. Set Up Payment Collection (Licensing)

For the dual-license model (free for education, paid for commercial):

**Option 1: Stripe (Recommended)**

1. Create Stripe account: stripe.com
2. Create products:
   - "EditorWatch Startup License" - $500/year
   - "EditorWatch SMB License" - $2,500/year
3. Create payment links for each product
4. Add to LICENSE.md:
```markdown
To purchase a commercial license:
- Startup: https://buy.stripe.com/your-link-1
- SMB: https://buy.stripe.com/your-link-2
- Enterprise: Contact via GitHub
```

**Option 2: GitHub Sponsors**

1. Enable GitHub Sponsors on your repo
2. Create tiers:
   - $500/year - Startup License
   - $2,500/year - SMB License
3. Add license delivery via email after payment

**Option 3: PayPal**

1. Create PayPal.me link
2. Add to LICENSE.md with instructions
3. Manually send license after payment confirmation

**Recommended Setup:**
- Stripe for automated payment + license delivery
- Add webhook to send license keys automatically
- Store purchased licenses in database

## Usage Workflow

### For Instructors:

1. Log in to dashboard: `https://your-railway-url.up.railway.app`
2. Create assignment
3. Download `.editorwatch` config file
4. Add to assignment starter code
5. Distribute to students via LMS

### For Students:

1. Download assignment folder
2. Open in VS Code (with EditorWatch extension installed)
3. Click "Enable" when prompted
4. Work on assignment
5. Click "Submit" when done

## Environment Variables Reference

**Required:**
- `DATABASE_URL` - PostgreSQL connection (Railway auto-sets)
- `REDIS_URL` - Redis connection (Railway auto-sets)
- `SECRET_KEY` - Flask session secret
- `ENCRYPTION_KEY` - Fernet encryption key
- `ADMIN_USERNAME` - Dashboard login
- `ADMIN_PASSWORD` - Dashboard password

**Optional:**
- `PORT` - Server port (default: 5000, Railway auto-sets)

## Testing

**Test Extension Locally:**
1. Open `extension/` in VS Code
2. Press F5
3. Create a test folder with `.editorwatch` file
4. Test monitoring and submission

**Test Backend Locally:**
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start worker
cd analysis
python -m rq.worker analysis

# Terminal 3: Start Flask
cd backend
python app.py
```

## Cost Estimates

**Railway:**
- Hobby Plan: $5/month (includes PostgreSQL + Redis)
- Usage: ~$0.10/GB bandwidth
- Total: $5-10/month for 100 students

**VS Code Marketplace:**
- Free to publish

**Domain (Optional):**
- $10-15/year

## Security Checklist

- [ ] Change default admin credentials
- [ ] Use strong SECRET_KEY
- [ ] Enable HTTPS (Railway provides free SSL)
- [ ] Review student consent workflow
- [ ] Set up data retention policy
- [ ] Add rate limiting (optional)

## Support

For issues:
- Extension: GitHub Issues
- Commercial licenses: Email in GitHub profile
- Documentation: See ARCHITECTURE.md

## Next Steps

1. ✅ Deploy backend to Railway
2. ✅ Publish extension to marketplace
3. ✅ Set up payment collection
4. Create assignment templates
5. Write instructor documentation
6. Add analytics dashboard
7. Implement data export for GDPR compliance

---

**Total setup time: ~2 hours**
