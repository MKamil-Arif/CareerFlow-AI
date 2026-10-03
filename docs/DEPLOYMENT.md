# Deploying CareerFlow AI for free

CareerFlow AI is one Docker container: FastAPI serves both the API and the frontend, and it keeps no data on disk. That makes it a good fit for free tiers whose filesystems are wiped on every restart.

Before you start:

1. Push the project to GitHub. `.env` is git-ignored, so your keys stay on your computer.
2. Have your AI keys ready: a Groq key and/or a Gemini key. Without keys the site still works in offline mode.
3. Optional: run `python -m app.check_ai` locally (see the README) to confirm the keys work.

---

## Option A — Render (recommended)

Free web service: 512 MB RAM, 750 instance hours a month, sleeps after 15 minutes without traffic, about a minute to wake up. No credit card needed.

1. Sign in at https://render.com with GitHub.
2. Click **New → Blueprint** and choose your repository. Render reads `render.yaml`.
3. When prompted, paste `GROQ_API_KEY` and/or `GEMINI_API_KEY`. Leave either one blank if you don't use it.
4. Click **Apply**. The first build takes a few minutes. Your site will be at `https://careerflow-ai.onrender.com` (or a similar name).
5. Open `https://<your-app>.onrender.com/api/health` and check that `"ai": {"configured": true}`.

Without the blueprint: **New → Web Service**, pick the repo, choose **Docker** as the runtime and the **Free** instance type, set the health check path to `/api/health`, and add the environment variables below.

Updates deploy automatically on every push to `main`.

## Option B — Hugging Face Spaces

Free Docker Space on CPU hardware, with more memory than Render's free tier. Spaces also go to sleep when unused.

1. Create a Space at https://huggingface.co/new-space and choose **Docker → Blank** as the SDK.
2. Push this repository to the Space (`git remote add space https://huggingface.co/spaces/<user>/<space>` and then `git push space main`).
3. Put this block at the **very top of `README.md` in the Space** (Spaces read their settings from it):

   ```yaml
   ---
   title: CareerFlow AI
   emoji: 🎯
   colorFrom: indigo
   colorTo: purple
   sdk: docker
   app_port: 8000
   pinned: false
   ---
   ```

4. In **Settings → Variables and secrets**, add `GROQ_API_KEY` and/or `GEMINI_API_KEY` as **secrets**, and `APP_ENV=production` as a variable.
5. The Space builds from the `Dockerfile` and serves at `https://<user>-<space>.hf.space`.

## Any other Docker host

```bash
docker build -t careerflow-ai .
docker run -p 8000:8000 -e GROQ_API_KEY=... -e GEMINI_API_KEY=... careerflow-ai
```

The container listens on `$PORT` (default 8000), so hosts that set `PORT` (Koyeb, Railway, Fly.io, Google Cloud Run) work without changes.

---

## Environment variables

| Name | Default | Notes |
|---|---|---|
| `GROQ_API_KEY` | — | Secret. Groq is tried first. |
| `GEMINI_API_KEY` | — | Secret. Used if Groq is missing or fails. |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Any Groq chat model ID. |
| `GEMINI_MODEL` | `gemini-3.7-flash` | Any Gemini model ID. |
| `APP_ENV` | `development` (`production` in Docker) | `production` enables HSTS and turns off the localhost CORS defaults. |
| `CORS_ORIGINS` | — | Only if the frontend is on another domain (comma separated). |
| `RATE_LIMIT_AI_PER_MINUTE` | `30` | Per visitor IP, for endpoints that call AI. `0` turns the limit off. |
| `RATE_LIMIT_DEFAULT_PER_MINUTE` | `120` | Per visitor IP, for everything else. |
| `MAX_UPLOAD_MB` | `5` | Largest resume PDF accepted. |
| `AI_TIMEOUT_SECONDS` | `25` | Time allowed for each AI provider call. |
| `LOG_LEVEL` | `INFO` | Provider failures are logged at WARNING. |

## Going public — checklist

- [ ] Set keys only in the host's secrets panel. Never commit `.env`.
- [ ] Set spending limits or usage alerts in the Groq and Gemini consoles. A public site can be abused, and the built-in rate limit is a first line of defence, not a guarantee.
- [ ] Check `/api/health` after each deploy.
- [ ] Watch the host's logs for `Groq failed:` / `Gemini failed:` warnings.
- [ ] Add a privacy notice if you collect real users' resumes. Profile text is sent to the AI provider for analysis.
- [ ] Optional: add a custom domain in the Render or Hugging Face settings (free on both).

## Known free-tier limits

- **Cold starts:** the first request after the app sleeps takes about a minute. The frontend allows 60 seconds per request and shows a "server may be waking up" message.
- **Rate limits are per instance and in memory:** they reset when the instance restarts. That's fine for one free instance.
- **Bandwidth:** Render's free workspace includes 5 GB a month. Each page load is roughly 100 KB plus fonts, which is plenty for a portfolio project.
