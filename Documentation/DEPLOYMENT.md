# EditorWatch Deployment Guide

## Step-by-Step Deployment Instructions

### Part 1: Deploy Backend to Railway (15 minutes)

#### 1.1 Prepare GitHub Repository

```bash
# Navigate to your editorwatch directory
cd editorwatch

# The project is structured for Railway deployment:
# - app.py and models.py at root (Flask app)
# - requirements.txt at root (all dependencies)
# - Procfile at root (tells Railway how to run)
# - templates/ at root (HTML files)
# - analysis/ subdirectory (worker code)
# - extension/ subdirectory (VS Code extension - not deployed to Railway)

# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial EditorWatch deployment"

# Create GitHub repository (on github.com)
# Then add remote and push:
git remote add origin https://github.com/YOURUSERNAME/editorwatch.git
git branch -M main
git push -u origin main
```

#### 1.2 Deploy on Railway

1. **Sign up for Railway:**
   - Go to https://railway.app
   - Click "Login with GitHub"
   - Authorize Railway to access your repos

2. **Create New Project:**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose `editorwatch` repository
   - Railway will automatically detect Python and start deployment

3. **Add PostgreSQL:**
   - In your project dashboard, click "+ New"
   - Select "Database" → "PostgreSQL"
   - Railway automatically creates `DATABASE_URL` environment variable

4. **Add Redis:**
   - Click "+ New" again
   - Select "Database" → "Redis"
   - Railway automatically creates `REDIS_URL` environment variable

5. **Configure Environment Variables:**
   - Click on your web service
   - Go to "Variables" tab
   - Add the following:

   ```
   SECRET_KEY = [generate with: python -c "import secrets; print(secrets.token_hex(32))"]
   ENCRYPTION_KEY = [generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"]
   ADMIN_USERNAME = admin
   ADMIN_PASSWORD = [choose a strong password]
   ```

6. **Get Your Deployment URL:**
   - Go to "Settings" tab
   - Under "Domains", you'll see your Railway URL
   - Example: `editorwatch-production-a1b2.up.railway.app`
   - Copy this - you'll need it!

7. **Verify Deployment:**
   - Visit your Railway URL
   - You should see the login page
   - Login with your ADMIN_USERNAME and ADMIN_PASSWORD

#### 1.3 Optional: Add Custom Domain

If you own a domain:

1. In Railway → Settings → Domains
2. Click "Add Domain"
3. Enter your domain (e.g., `editorwatch.yourdomain.com`)
4. Add the CNAME record to your DNS:
   ```
   CNAME editorwatch -> editorwatch-production-a1b2.up.railway.app
   ```

---

### Part 2: Publish Extension to VS Code Marketplace (30 minutes)

#### 2.1 Create Azure DevOps Account & Publisher

1. **Create Azure DevOps Account:**
   - Go to https://dev.azure.com
   - Sign in with Microsoft account (create one if needed)

2. **Create Personal Access Token (PAT):**
   - Click user icon (top right) → "Personal access tokens"
   - Click "+ New Token"
   - Name: "VS Code Extension Publishing"
   - Organization: All accessible organizations
   - Scopes: Custom defined → "Marketplace" → check "Publish"
   - Click "Create"
   - **IMPORTANT:** Copy and save the token immediately (you won't see it again)

3. **Create Publisher:**
   - Go to https://marketplace.visualstudio.com/manage
   - Click "Create publisher"
   - Publisher ID: Choose a unique name (e.g., "yourname-editorwatch")
   - Display Name: Your name or company
   - Click "Create"

#### 2.2 Update Extension Configuration

Edit `extension/package.json`:

```json
{
  "name": "editorwatch",
  "publisher": "YOUR-PUBLISHER-ID",  // Change this!
  "repository": {
    "type": "git",
    "url": "https://github.com/YOURUSERNAME/editorwatch"  // Change this!
  }
}
```

#### 2.3 Install Publishing Tools

```bash
# Install vsce globally
npm install -g @vscode/vsce

# Navigate to extension directory
cd extension

# Install dependencies
npm install
```

#### 2.4 Package and Publish

```bash
# Login to publisher account
vsce login YOUR-PUBLISHER-ID
# Enter your PAT when prompted

# Package the extension (creates .vsix file)
vsce package

# If successful, publish:
vsce publish
```

#### 2.5 Verify Publication

1. Go to https://marketplace.visualstudio.com/
2. Search for "editorwatch"
3. Your extension should appear within 5-10 minutes
4. Direct URL: `https://marketplace.visualstudio.com/items?itemName=YOUR-PUBLISHER-ID.editorwatch`

#### 2.6 Update Extension with Server URL

After you have your Railway deployment URL, update your extension:

1. Create a config file or update the extension to use your server URL
2. Bump version in `package.json`: `"version": "0.1.1"`
3. Publish update:
   ```bash
   vsce publish
   ```

---

### Part 3: Set Up Payment Collection for Commercial Licenses (20 minutes)

#### Option A: Stripe (Recommended - Most Professional)

1. **Create Stripe Account:**
   - Go to https://stripe.com
   - Sign up for account
   - Complete verification

2. **Create Products:**
   - Dashboard → Products → "+ Add Product"
   
   **Product 1: Startup License**
   - Name: EditorWatch Commercial License (Startup)
   - Description: For companies with <$1M revenue
   - Price: $500 USD
   - Billing: Recurring, annually
   - Click "Save product"
   - Click "Create payment link"
   - Copy the link (e.g., `https://buy.stripe.com/abc123xyz`)

   **Product 2: SMB License**
   - Name: EditorWatch Commercial License (SMB)
   - Description: For companies with $1M-$10M revenue
   - Price: $2,500 USD
   - Billing: Recurring, annually
   - Create payment link

3. **Update LICENSE.md:**

```markdown
## Commercial Use (Paid License Required)

To purchase a commercial license:

**Startup (<$1M revenue): $500/year**
[Purchase Now](https://buy.stripe.com/YOUR-STARTUP-LINK)

**SMB ($1M-$10M revenue): $2,500/year**
[Purchase Now](https://buy.stripe.com/YOUR-SMB-LINK)

**Enterprise (>$10M revenue):**
Contact: your-email@example.com

After purchase, you'll receive your license key via email within 24 hours.
```

4. **Set Up Email Notifications:**
   - Stripe Dashboard → Settings → Emails
   - Enable "Successful payments" notifications
   - You'll get email when someone purchases

5. **Deliver Licenses:**
   - Manual: Send license key via email after payment
   - Automated: Set up Stripe webhook to auto-send (advanced)

#### Option B: GitHub Sponsors (Simpler but Less Professional)

1. **Enable GitHub Sponsors:**
   - Go to your GitHub profile settings
   - Enable GitHub Sponsors
   - Complete bank information

2. **Create Sponsor Tiers:**
   - $500/year - Commercial License (Startup)
   - $2,500/year - Commercial License (SMB)
   - Add benefit: "Commercial usage rights + license key"

3. **Update LICENSE.md:**
```markdown
To purchase: Sponsor via GitHub Sponsors
https://github.com/sponsors/YOURUSERNAME

After sponsoring, create a GitHub issue with tag `license-request`
```

#### Option C: PayPal (Simplest but Fully Manual)

1. **Create PayPal.me Link:**
   - Sign up at paypal.com
   - Get your PayPal.me link
   - Example: `https://paypal.me/yourname`

2. **Update LICENSE.md:**
```markdown
To purchase a license:

1. Send payment via PayPal: https://paypal.me/yourname
   - Startup: $500
   - SMB: $2,500
   - Include your company name and email in message

2. Email your-email@example.com with:
   - PayPal transaction ID
   - Company name
   - Use case

3. Receive license key within 24 hours
```

---

### Part 4: Final Configuration Checklist

#### Update URLs in Code

1. **Extension (`extension/package.json`):**
   ```json
   "repository": {
     "url": "https://github.com/YOURUSERNAME/editorwatch"
   }
   ```

2. **README.md:**
   - Update deployment URL examples
   - Update GitHub links
   - Add your contact information

3. **LICENSE.md:**
   - Add payment links
   - Add your contact email

#### Create Example Assignment

1. Log into your Railway dashboard
2. Create a test assignment
3. Download `.editorwatch` config
4. Test the full workflow:
   - Open folder with config in VS Code
   - Enable monitoring
   - Make some edits
   - Submit assignment
   - View in dashboard

---

### Part 5: Marketing & Distribution

#### 5.1 Create Landing Page (Optional)

Simple static site on GitHub Pages:

```bash
# Create docs/ folder
mkdir docs
cd docs

# Create index.html
# Deploy to GitHub Pages via Settings → Pages
```

#### 5.2 Announce

- Post on Twitter/X with #edtech #academicintegrity
- Share in r/learnprogramming, r/cscareerquestions
- Contact CS professors you know
- Post on Hacker News "Show HN: EditorWatch - Making cheating harder than learning"

#### 5.3 Create Demo Video

- Record 3-minute walkthrough
- Upload to YouTube
- Embed in README

---

## Complete Cost Breakdown

### Monthly Costs:
- **Railway Hobby:** $5/month (includes PostgreSQL + Redis)
- **Domain (optional):** ~$1/month ($12/year)
- **Total:** $5-6/month

### One-Time Costs:
- **VS Code Publisher Registration:** $0 (free)
- **Stripe/PayPal:** $0 setup fee (transaction fees apply to sales)

### Revenue Potential:
- 10 bootcamps × $500 = $5,000/year
- 5 companies × $2,500 = $12,500/year
- **Total potential:** $17,500/year

**Net profit:** ~$17,400/year (after $60-100 hosting)

---

## Troubleshooting

### Railway Deployment Issues

**Problem:** Build fails
```bash
# Check logs in Railway dashboard
# Common fix: ensure requirements.txt is at root
```

**Problem:** Database connection error
```bash
# Verify DATABASE_URL environment variable is set
# Check PostgreSQL service is running
```

### Extension Publishing Issues

**Problem:** `vsce publish` fails with auth error
```bash
# Re-login
vsce logout
vsce login YOUR-PUBLISHER-ID
```

**Problem:** Extension not appearing in marketplace
```bash
# Wait 10-15 minutes
# Check publisher dashboard for status
```

### Payment Collection Issues

**Problem:** Stripe payments not received
```bash
# Check Stripe dashboard → Payments
# Verify webhook URL (if using automation)
# Check email notifications are enabled
```

---

## Next Steps After Deployment

1. ✅ Test full workflow end-to-end
2. ✅ Create documentation for instructors
3. ✅ Prepare demo assignment
4. Monitor logs and fix bugs
5. Gather feedback from beta users
6. Implement feature requests
7. Write blog post about the project

---

## Support Resources

- **Railway Docs:** https://docs.railway.app
- **VS Code Publishing:** https://code.visualstudio.com/api/working-with-extensions/publishing-extension
- **Stripe Docs:** https://stripe.com/docs
- **GitHub Issues:** For bug reports and feature requests

---

**Estimated Total Time:** 60-90 minutes

**Congratulations! 🎉 EditorWatch is now live!**
