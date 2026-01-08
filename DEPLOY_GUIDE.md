# 🚀 Vercel Deployment Guide - Step by Step

Complete guide to deploy PostgreSQL Query Tuning Advisor to Vercel.

---

## Step 1: Generate Required Keys

Open your terminal and run these commands to generate the keys you'll need:

### Generate SECRET_KEY
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
**Copy and save this key!**

### Generate ENCRYPTION_KEY
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
**Copy and save this key!**

---

## Step 2: Get Your GROQ API Key (FREE)

1. Go to **https://console.groq.com/**
2. Sign up or login with Google/GitHub
3. Go to **API Keys** section
4. Click **Create API Key**
5. **Copy and save the key!**

---

## Step 3: Create a GitHub Repository

1. Go to **https://github.com/new**
2. Name: `tuning-buddy` (or any name you prefer)
3. Keep it **Private** or **Public**
4. Click **Create repository**
5. Don't add README (you already have one)

### Push your code:
Run these commands in your project folder:

```bash
cd c:\Users\muham\Desktop\tuning-buddy

# Initialize git (if not done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - PostgreSQL Query Tuning Advisor"

# Add your GitHub repo (replace YOUR_USERNAME)
git remote add origin https://github.com/Athoillah21/tuning-buddy.git

# Push
git branch -M main
git push -u origin main
```

---

## Step 4: Create Vercel Account

1. Go to **https://vercel.com/**
2. Click **Sign Up**
3. Choose **Continue with GitHub** (recommended - easier!)
4. Authorize Vercel to access your GitHub

---

## Step 5: Create Vercel Postgres Database

1. After login, go to **https://vercel.com/dashboard**
2. Click **Storage** in the left sidebar
3. Click **Create Database**
4. Select **Postgres**
5. Choose a name (e.g., `tuning-buddy-db`)
6. Select region closest to you
7. Click **Create**
8. After creation, go to the database and copy the **DATABASE_URL** from the **.env.local** tab

---

## Step 6: Deploy the Project

### Option A: Deploy via Vercel Website (Easiest)

1. Go to **https://vercel.com/new**
2. Click **Import Git Repository**
3. Select your `tuning-buddy` repository
4. Click **Import**
5. **BEFORE clicking Deploy**, expand **Environment Variables**
6. Add these variables one by one:

| Key | Value |
|-----|-------|
| `SECRET_KEY` | (paste the key you generated in Step 1) |
| `DEBUG` | `False` |
| `DATABASE_URL` | (paste from Vercel Postgres - Step 5) |
| `ENCRYPTION_KEY` | (paste the key you generated in Step 1) |
| `GROQ_API_KEY` | (paste your Groq API key from Step 2) |

7. Click **Deploy**
8. Wait for deployment (2-3 minutes)

---

## Step 7: Run Database Migrations

After deployment, you need to run migrations. 

### Option 1: Using Vercel Dashboard
1. Go to your project on Vercel
2. Click **Functions** tab
3. Look for any errors - if migrations didn't run, continue to Option 2

### Option 2: Using Vercel CLI
```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Link to your project
vercel link

# Run migrations
vercel env pull .env.local
python manage.py migrate
```

### Option 3: Add Build Command
1. Go to Vercel Dashboard → Your Project → Settings → General
2. In **Build & Development Settings**, set:
   - **Build Command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
3. Redeploy

---

## Step 8: Visit Your App!

After deployment, Vercel will give you a URL like:
```
https://tuning-buddy-xxxxx.vercel.app
```

Click it to open your app! 🎉

---

## Troubleshooting

### "Application Error" on first visit
- Check Vercel Logs: Dashboard → Your Project → Functions → View Logs
- Usually means migrations didn't run - see Step 7

### "No AI provider configured"
- Make sure `GROQ_API_KEY` is set in Environment Variables
- Redeploy after adding

### Database connection errors
- Make sure `DATABASE_URL` is correct
- Check if Postgres is linked to your project

---

## Summary: What You Need

| Item | Where to Get It |
|------|-----------------|
| SECRET_KEY | Generate with Python command |
| ENCRYPTION_KEY | Generate with Python command |
| DATABASE_URL | Vercel Postgres dashboard |
| GROQ_API_KEY | https://console.groq.com/ |

---

## Quick Reference: Environment Variables for Vercel

```
SECRET_KEY=your-generated-django-secret-key
DEBUG=False
DATABASE_URL=postgres://user:pass@host:5432/dbname
ENCRYPTION_KEY=your-generated-fernet-key
GROQ_API_KEY=gsk_your_groq_api_key_here
```
