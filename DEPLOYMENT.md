# Deployment Guide

**Stack:** Qdrant Cloud → Supabase → Render (backend) → Vercel (frontend)

Complete this in order. Each step gives you a value you'll need in the next one.

---

## Step 1 — Qdrant Cloud (Vector DB)

1. Go to **[cloud.qdrant.io](https://cloud.qdrant.io)** → Sign up (free)
2. Click **Create Cluster** → Free tier → Region: `GCP / US East` → Create
3. Once running, click the cluster → **API Keys** → Create API Key → Copy it
4. Copy the **Cluster URL** (looks like `https://xxxx.us-east4-0.gcp.cloud.qdrant.io`)

Save:
```
QDRANT_URL=https://xxxx.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=your-api-key-here
```

---

## Step 2 — Supabase (PostgreSQL for sessions)

1. Go to **[supabase.com](https://supabase.com)** → New project
2. Choose a region close to your Render region
3. Wait for provisioning (~1 min)
4. Go to **Settings → Database → Connection string → URI**
5. Copy the URI — it looks like:
   ```
   postgres://postgres.xxxx:PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
   ```
6. Replace `[YOUR-PASSWORD]` with the password you set during project creation

Save:
```
DATABASE_URL=postgres://postgres.xxxx:PASSWORD@aws-0-xxx.pooler.supabase.com:5432/postgres
```

> The app auto-creates the `sessions` and `messages` tables on first startup — no manual SQL needed.

---

## Step 3 — Clerk (Auth — production keys)

1. Go to **[clerk.com](https://clerk.com)** → Your application → **API Keys**
2. Copy **Publishable Key** (`pk_live_...`) and **Secret Key** (`sk_live_...`)
3. Go to **JWT Templates** → Find the default template → copy the JWKS URL:
   ```
   https://YOUR_DOMAIN.clerk.accounts.dev/.well-known/jwks.json
   ```
4. Go to **Domains** → Add your Vercel URL once you have it (Step 5)

Save:
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_xxxx
CLERK_SECRET_KEY=sk_live_xxxx
CLERK_JWKS_URL=https://YOUR_DOMAIN.clerk.accounts.dev/.well-known/jwks.json
```

---

## Step 4 — Backend on Render

### 4a. Push to GitHub first (if not done)
```bash
cd enterprise-knowledge-assistant
git init
git add .
git commit -m "feat: initial commit"
git remote add origin https://github.com/YOUR_USERNAME/enterprise-knowledge-assistant.git
git branch -M main
git push -u origin main
```

### 4b. Create Render service
1. Go to **[render.com](https://render.com)** → New → **Web Service**
2. Connect your GitHub repo → Select `enterprise-knowledge-assistant`
3. Settings:
   - **Name:** `eka-backend`
   - **Region:** Singapore (or Oregon)
   - **Branch:** `main`
   - **Runtime:** Docker
   - **Dockerfile Path:** `./backend/Dockerfile`
   - **Docker Context:** `./backend`
   - **Plan:** Free

4. Under **Environment Variables**, add each of these:

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | `gsk_xxxx` |
| `QDRANT_URL` | from Step 1 |
| `QDRANT_API_KEY` | from Step 1 |
| `QDRANT_COLLECTION_NAME` | `enterprise_docs` |
| `DATABASE_URL` | from Step 2 |
| `CLERK_SECRET_KEY` | from Step 3 |
| `CLERK_JWKS_URL` | from Step 3 |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app` (fill after Step 5) |
| `ENVIRONMENT` | `production` |
| `OPENBLAS_NUM_THREADS` | `1` |
| `OMP_NUM_THREADS` | `1` |
| `TOKENIZERS_PARALLELISM` | `false` |

5. Click **Create Web Service**

> **First deploy takes 8–12 minutes** — Docker builds ML model layers. Subsequent deploys are faster (layers cached).

6. Once live, copy your backend URL: `https://eka-backend.onrender.com`

---

## Step 5 — Frontend on Vercel

1. Go to **[vercel.com](https://vercel.com)** → New Project → Import your GitHub repo
2. Set **Root Directory** to `frontend`
3. Framework: **Next.js** (auto-detected)
4. Add these **Environment Variables**:

| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `pk_live_xxxx` |
| `CLERK_SECRET_KEY` | `sk_live_xxxx` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` | `/chat` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL` | `/chat` |
| `NEXT_PUBLIC_API_URL` | `https://eka-backend.onrender.com` |

5. Click **Deploy**
6. Copy your Vercel URL: `https://your-app.vercel.app`

---

## Step 6 — Wire everything together

### Update Render: add your Vercel URL to ALLOWED_ORIGINS
1. Render Dashboard → eka-backend → Environment
2. Update `ALLOWED_ORIGINS` → `https://your-app.vercel.app`
3. Render auto-redeploys

### Update Clerk: add your Vercel URL as allowed domain
1. Clerk Dashboard → Domains → Add `your-app.vercel.app`

---

## Step 7 — Verify deployment

```bash
# Backend health check
curl https://eka-backend.onrender.com/health

# Expected response:
# {"status":"ok","environment":"production","qdrant":"ok","database":"ok"}
```

Open `https://your-app.vercel.app` → sign up → upload a document → ask a question.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Backend 503 on first request | Render free tier cold start (~30s) | Wait 30s and retry |
| `qdrant: "error"` in /health | Wrong QDRANT_URL or API key | Check Render env vars |
| `database: "error"` in /health | Wrong DATABASE_URL | Check Supabase connection string — must include password |
| CORS error in browser | ALLOWED_ORIGINS missing Vercel URL | Update env var in Render + redeploy |
| Clerk 401 on all requests | Wrong CLERK_JWKS_URL | Must be the `.well-known/jwks.json` URL, not the secret key |
| First deploy takes >15 min | ML models downloading | Normal for first build. Layers cached after that |

---

## Environment Variables Reference

### Backend (Render)
```env
GROQ_API_KEY=gsk_xxxx
QDRANT_URL=https://xxxx.cloud.qdrant.io
QDRANT_API_KEY=xxxx
QDRANT_COLLECTION_NAME=enterprise_docs
DATABASE_URL=postgres://postgres.xxxx:PASSWORD@aws-0-xxx.pooler.supabase.com:5432/postgres
CLERK_SECRET_KEY=sk_live_xxxx
CLERK_JWKS_URL=https://YOUR_DOMAIN.clerk.accounts.dev/.well-known/jwks.json
ALLOWED_ORIGINS=https://your-app.vercel.app
ENVIRONMENT=production
OPENBLAS_NUM_THREADS=1
OMP_NUM_THREADS=1
TOKENIZERS_PARALLELISM=false
```

### Frontend (Vercel)
```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_xxxx
CLERK_SECRET_KEY=sk_live_xxxx
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/chat
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/chat
NEXT_PUBLIC_API_URL=https://eka-backend.onrender.com
```
