# Push to GitHub & deploy on Vercel

## 1. One-time: connect this folder to your GitHub repo

If the repo **already exists** on GitHub (empty or with a README):

```powershell
cd C:\Apps\AIChecked
git init
git add .
git commit -m "AIChecked.com — quick scan site + research tooling"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/aichecked.git
git push -u origin main
```

Replace `YOUR_USERNAME/aichecked` with your actual repo path.

If the remote **already has commits** (e.g. Vercel created a README):

```powershell
git pull origin main --allow-unrelated-histories
# resolve any conflicts, then:
git push -u origin main
```

If the repo **does not exist** yet:

```powershell
gh repo create aichecked --public --source=. --remote=origin --push
```

## 2. Vercel project settings

In [vercel.com](https://vercel.com) → your **aichecked** project:

| Setting | Value |
|---------|--------|
| **Framework Preset** | Other |
| **Root Directory** | `.` (repo root) |
| **Build Command** | *(leave empty)* |
| **Output Directory** | *(leave empty)* |
| **Install Command** | `pip install -r requirements.txt` |

Environment variable (optional — also set in `vercel.json`):

| Name | Value |
|------|--------|
| `QUICK_ONLY` | `1` |

Connect the project to your GitHub repo if not already: **Settings → Git → Connect**.

## 3. Custom domain (aichecked.com)

Vercel dashboard → **Project → Settings → Domains**:

1. Add `aichecked.com` and `www.aichecked.com`
2. At your domain registrar, set DNS as Vercel instructs:

   - **A** record `@` → `76.76.21.21` (Vercel's IP — confirm in dashboard)
   - **CNAME** `www` → `cname.vercel-dns.com`

## 4. What gets deployed

- `public/` → static site (HTML/CSS/JS)
- `api/health.py` → serverless `/api/health`
- `api/scan.py` → serverless `/api/scan`
- **Quick scan only** on Vercel (no PyTorch — too large for serverless)

Research tools (`main.py --evaluate`, deep scan) stay in the repo for **local** use:

```powershell
pip install -r requirements-research.txt
$env:QUICK_ONLY="0"
uvicorn server:app --reload
```

## 5. After every change

```powershell
git add .
git commit -m "Describe your change"
git push
```

Vercel redeploys automatically on push to `main`.

## Troubleshooting

- **404 on /** — ensure `public/index.html` exists and is committed
- **API 500** — Vercel → Deployments → Function logs
- **Module not found** — `requirements.txt` must list `fastapi` (not `requirements-research.txt`)
