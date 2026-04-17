# AI Agents Daily Digest Bot

Pulls the last 24 hours of AI / agent / LLM-tooling news from curated RSS feeds, AI-influencer Twitter handles (via Nitter RSS), and optionally Tavily web search. Filters for relevance, has an LLM (Google Gemma via OpenRouter — free tier) write a TLDR grouped by theme, and emails it to you every morning.

Runs entirely on GitHub Actions — no servers, free forever (within GitHub's generous free tier for public repos, and 2000 min/mo for private).

## What you get

An email every morning that looks like:

```
## Model releases
- Anthropic shipped Claude 4.7 Opus with improved tool-use... [Anthropic](...)
- ...

## Agent frameworks
- LangGraph 1.0 adds durable execution... [LangChain blog](...)

## Research worth reading
- ...

**Why it matters:** short one-liner
```

## Setup (10 minutes)

### 1. Fork or copy this repo to your GitHub account

Make it private if you want.

### 2. Get the required API keys

- **OpenRouter API key** → https://openrouter.ai/keys. The default model (`google/gemma-3-27b-it:free`) is free — no credit card needed. Free-tier rate limits (~20 req/min, ~200 req/day) are more than enough for one daily run.
- **Resend API key** → https://resend.com → sign up (free) → API Keys → Create.
- *(Optional)* **Tavily API key** → https://tavily.com → free tier gives 1k searches/month. Skip this and it'll just use RSS + Twitter.

### 3. Add them as GitHub Actions secrets

In your repo: **Settings → Secrets and variables → Actions → New repository secret**. Add:

| Name | Value |
|---|---|
| `OPENROUTER_API_KEY` | your OpenRouter key |
| `RESEND_API_KEY` | your Resend key |
| `DIGEST_TO_EMAIL` | the email address you want the digest sent to |
| `DIGEST_FROM_EMAIL` | *(optional)* e.g. `AI Digest <onboarding@resend.dev>` — the default works without domain verification |
| `TAVILY_API_KEY` | *(optional)* your Tavily key |
| `UNSUB_SECRET` | long random string; must match the value set in Vercel env (signs unsubscribe links) |

Also add a **repo variable** (Settings → Secrets and variables → Actions → **Variables** tab):

| Name | Value |
|---|---|
| `PUBLIC_BASE_URL` | the deployed Vercel URL, e.g. `https://ai-digest-bot.vercel.app` |

### 4. Test it

Go to the **Actions** tab → **Daily AI Digest** → **Run workflow**. Should finish in ~30s and you'll get an email.

### 5. Adjust the schedule

Edit `.github/workflows/daily-digest.yml`. The cron is in **UTC**. For 7 AM IST use `30 1 * * *`. For 7 AM ET use `0 11 * * *` (standard time) or `0 12 * * *` (during EDT).

## Tuning

- **RSS sources**: edit `RSS_FEEDS` in `src/sources.py` to add/remove feeds.
- **Twitter handles**: edit `TWITTER_HANDLES` in `src/sources.py`. The bot fetches each via Nitter RSS. Public Nitter instances break frequently — if Twitter items stop appearing, refresh `NITTER_INSTANCES` from the [Nitter instance list](https://github.com/zedeus/nitter/wiki/Instances).
- **Relevance filter**: edit `RELEVANCE_KEYWORDS` in the same file. Items must match at least one keyword.
- **Summary style**: edit `SYSTEM_PROMPT` in `src/summarize.py`. This is where you control tone, structure, and what gets prioritized.
- **Model**: change `MODEL` at the top of `src/summarize.py`. Other free options on OpenRouter include `meta-llama/llama-3.3-70b-instruct:free` and `deepseek/deepseek-chat-v3.1:free`. Any paid OpenRouter model works too (e.g. `anthropic/claude-sonnet-4.5`, `openai/gpt-4o-mini`).

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env     # then edit .env with your real keys
python src/main.py
```

`.env` is gitignored; never commit real secrets. The loader will fail fast with a clear error if a required variable is missing.

## Public subscription page

A minimal signup form lives in `web/` and two Vercel serverless functions in `api/` handle writes to `subscribers.json`. People submit their email, a commit appends them to the list, and the next daily digest goes out to everyone on the list. Each email has a one-click unsubscribe link that HMAC-verifies the address and removes it via another commit.

### Deploy the frontend

1. **Create a fine-grained GitHub PAT** at https://github.com/settings/personal-access-tokens with:
   - Repository access: this repo only
   - Repository permissions → **Contents: Read and write**
2. **Import the repo on Vercel** (https://vercel.com/new). Vercel picks up `vercel.json` automatically.
3. In Vercel **Settings → Environment Variables**, add:

   | Name | Value |
   |---|---|
   | `GITHUB_TOKEN` | the PAT from step 1 |
   | `GITHUB_REPO` | `your-username/ai-digest-bot` |
   | `GITHUB_BRANCH` | *(optional)* branch to commit to, default `main` |
   | `UNSUB_SECRET` | same random string you set as a GitHub Actions secret |

4. Deploy. The form at the root URL will start accepting signups.

### How it fits together

- `subscribers.json` (repo root) — canonical list, committed to git.
- `web/index.html`, `web/unsubscribed.html` — static pages served by Vercel.
- `api/subscribe.py`, `api/unsubscribe.py` — Python serverless functions that read/write `subscribers.json` via the GitHub Contents API.
- `src/subscribers.py` — pipeline-side loader that reads `subscribers.json` from the checked-out working tree and mints HMAC-signed unsubscribe URLs with the same `UNSUB_SECRET`.
- `src/email_sender.send_digest_to_subscribers` — iterates the list, substituting `{{unsubscribe_url}}` per recipient.

If `subscribers.json` is empty, the pipeline falls back to `DIGEST_TO_EMAIL` so the single-user setup keeps working.

## Project layout

```
.
├── .github/workflows/daily-digest.yml   # Scheduler
├── .env.example                         # Template for local secrets
├── requirements.txt
├── vercel.json                          # Vercel config
├── subscribers.json                     # Canonical subscriber list
├── web/                                 # Static signup page
│   ├── index.html
│   └── unsubscribed.html
├── api/                                 # Vercel Python serverless functions
│   ├── _shared.py
│   ├── subscribe.py
│   └── unsubscribe.py
└── src/
    ├── main.py            # Orchestrator
    ├── config.py          # Env var loading + validation
    ├── sources.py         # RSS + Twitter + Tavily fetchers + relevance filter
    ├── summarize.py       # OpenRouter (Gemma) summarization
    ├── subscribers.py     # Subscriber list loader + unsubscribe-URL signer
    └── email_sender.py    # Resend client (single + fan-out)
```
