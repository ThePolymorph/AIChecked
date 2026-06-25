# Deploying AIChecked.com

## Two tiers (pick one)

| Tier | What users get | RAM | Hosting cost |
|------|----------------|-----|--------------|
| **Public site** (`QUICK_ONLY=1`) | Instant surface-pattern scan | ~64–128 MB | **$0–5/mo** |
| **Self-hosted research** (`QUICK_ONLY=0`) | + Binoculars deep scan | ~2 GB+ | Your machine / GPU VPS |

**For a free ad-hoc public site, use the public tier only.** Deep scan is research tooling — not something you want random visitors triggering.

## Public site (recommended)

```powershell
pip install -r requirements-web.txt
$env:QUICK_ONLY="1"
uvicorn api:app --host 0.0.0.0 --port 8000
```

Or Docker (~120 MB image, no PyTorch):

```powershell
docker build -f Dockerfile.web -t aichecked-web .
docker run -p 8000:8000 aichecked-web
```

No model downloads. No GPU. Thousands of quick scans fit on a $5/mo VPS or free Render/Railway hobby tier.

## Local dev with deep scan (optional)

```powershell
pip install -r requirements.txt
$env:QUICK_ONLY="0"
uvicorn server:app --reload --port 8000
```

First **Deep scan** downloads GPT-2 + GPT-2-medium (~1.5 GB). Set `LOAD_MODELS=1` only if you want that at startup.

## Production (aichecked.com)

### DNS

| Type | Name | Value |
|------|------|-------|
| A | `@` | your server IP |
| A | `www` | your server IP |

### Run with uvicorn + nginx

See `DEPLOY.md` in repo for systemd unit, nginx SSL config, and RAM notes.

Use **1 uvicorn worker** — each worker loads its own model copy.

### Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `QUICK_ONLY` | `1` | `1` = public site (no models). `0` = enable deep scan |
| `LOAD_MODELS` | `0` | `1` = preload GPT-2 at startup (only if `QUICK_ONLY=0`) |
| `OBSERVER_MODEL` | `gpt2` | Observer model |
| `PERFORMER_MODEL` | `gpt2-medium` | Performer model |
