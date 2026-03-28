# SEO Blog Engine

An AI-powered SEO content engine with a **local web UI**. Research keywords, generate optimized blog posts with images, update underperforming content using Google Search Console data, and publish directly to your CMS — all from a clean browser interface.

Works with **any AI provider** and **any major CMS platform**.

---

## Features

- **Local web UI** — no SaaS, no subscriptions, runs on your machine
- **Multi-platform** — WordPress, WooCommerce, Shopify, Wix, MongoDB (blog-poster)
- **Any AI provider** — Google Gemini, OpenAI, Anthropic Claude, Mistral, DeepSeek
- **GSC integration** — protect ranking pages, find page-2 opportunities, track performance
- **Live pipeline streaming** — watch every step in real time, abort anytime, download logs
- **Multi-site** — manage unlimited sites from one UI, each with its own config
- **Posts & Products** — browse published content and products with GSC stats on hover
- **Pipeline history** — every run logged with status, duration, and log preview
- **Manual Review Gate** — optionally hold generated content in a review queue; edit in the TipTap rich-text editor with AI chat refinement before publishing
- **Scheduled Automation** — create Daily / Weekly / Monthly / Custom cron schedules per site and mode; runs in-process via APScheduler with per-run log history

---

## Quick Start

> **Requirements:** Python 3.10+, Node.js 18+, Git Bash (Windows) or any Unix shell

```bash
git clone https://github.com/Nivnivu/perfect_seo.git
cd perfect_seo
./start.sh
```

The script installs all dependencies, starts the API on port 8000 and the UI on port 5173, and opens your browser automatically.

**First time:** Go to **Sites → Add Site** and follow the wizard to configure your first site.

---

## Setup

### 1. Add a site through the UI

Open `http://localhost:5173/sites` and click **Add Site**. The wizard walks you through:

1. Choose your CMS platform
2. Enter site name, domain, AI provider + API key
3. Enter platform credentials
4. (Optional) Connect Google Search Console
5. Add seed keywords and brand context
6. Review and save → creates `config.yoursite.yaml` in the project root

Or copy one of the example configs manually:

```bash
cp config.example.wordpress.yaml   config.mysite.yaml
cp config.example.woocommerce.yaml config.mysite.yaml
cp config.example.shopify.yaml     config.mysite.yaml
cp config.example.wix.yaml         config.mysite.yaml
cp config.example.mongodb.yaml     config.mysite.yaml   # blog-poster CMS users
```

---

### 2. Choose an AI provider

Add **one** of these blocks to your config:

#### Google Gemini (recommended — has image generation)
```yaml
gemini:
  api_key: "AIza..."                        # aistudio.google.com/app/apikey
  model: "gemini-2.5-flash"
  image_model: "imagen-4.0-fast-generate-001"
```

#### OpenAI
```yaml
openai:
  api_key: "sk-..."                         # platform.openai.com/api-keys
  model: "gpt-4.1"
  image_model: "dall-e-3"                   # optional
```

#### Anthropic Claude
```yaml
anthropic:
  api_key: "sk-ant-..."                     # console.anthropic.com/settings/keys
  model: "claude-sonnet-4-6"
```

#### Mistral AI
```yaml
mistral:
  api_key: "..."                            # console.mistral.ai/api-keys
  model: "mistral-large-latest"
```

#### DeepSeek
```yaml
deepseek:
  api_key: "sk-..."                         # platform.deepseek.com/api_keys
  model: "deepseek-chat"
```

---

### 3. Platform Credentials

#### WordPress

Uses the WordPress REST API v2 with an Application Password (no plugins needed).

```yaml
platform: wordpress

wordpress:
  site_url: "https://yourblog.com"
  username: "your-wp-username"
  app_password: "xxxx xxxx xxxx xxxx xxxx xxxx"
```

**How to get an Application Password:**
1. WordPress Admin → Users → Edit your user
2. Scroll to **Application Passwords** → Enter a name → **Add New**
3. Copy the generated password (shown only once)

---

#### WooCommerce

```yaml
platform: woocommerce

woocommerce:
  site_url: "https://yourstore.com"
  consumer_key: "ck_..."
  consumer_secret: "cs_..."
```

**How to get API keys:**
1. WooCommerce → Settings → Advanced → REST API
2. **Add Key** → permissions: **Read/Write**
3. Copy Consumer Key and Consumer Secret

---

#### Shopify

```yaml
platform: shopify

shopify:
  store_domain: "your-store.myshopify.com"
  admin_api_token: "shpat_..."
```

**How to get an Admin API token:**
1. Shopify Admin → Settings → Apps → Develop apps
2. Enable custom app development → Create an app
3. Admin API scopes: `read_content`, `write_content`, `read_products`, `write_products`
4. Install the app → copy the Admin API access token

---

#### Wix

```yaml
platform: wix

wix:
  api_key: "IST.eyJ..."
  site_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

**How to get Wix credentials:**
1. [Wix Dev Center](https://dev.wix.com) → API Keys
2. Create a key with **Blog** and **Stores** permissions
3. Your site ID is in your Wix dashboard URL

---

#### MongoDB (blog-poster)

For users of the [blog-poster](https://github.com/Nivnivu/blog-poster) open source CMS — a headless blog engine for React, Vue, and Next.js websites.

```yaml
platform: mongodb

mongodb:
  uri: "mongodb+srv://user:pass@cluster.mongodb.net/"
  database: "multiBlogDB"
  collection: "your_collection"

supabase:
  url: "https://xxxx.supabase.co"
  key: "your-service-role-key"
  bucket: "blog-poster"
```

**MongoDB Atlas:** Create a free cluster at [mongodb.com/atlas](https://www.mongodb.com/atlas) → Connect → Drivers → copy the URI.

**Supabase:** Create a project at [supabase.com](https://supabase.com) → Settings → API → copy URL and service_role key. Create a storage bucket named `blog-poster` (public).

---

### 4. Google Search Console (optional but recommended)

GSC enables: ranking protection, page-2 opportunity detection, CTR optimization, and the Analytics dashboard.

**Each user needs their own Google Cloud credentials.**

#### Step 1 — Create a Google Cloud project

1. [console.cloud.google.com](https://console.cloud.google.com) → New project
2. **APIs & Services → Library** → search **Google Search Console API** → Enable

#### Step 2 — Create OAuth credentials

1. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
2. Application type: **Desktop app**
3. Download the JSON → save to project root as `client_secret_xxx.json`

#### Step 3 — OAuth consent screen

1. **APIs & Services → OAuth consent screen** → User type: **External**
2. Add scope: `https://www.googleapis.com/auth/webmasters.readonly`
3. Add yourself as a **Test user**
4. Keep the app in **Testing** mode — no Google review needed for personal/team use

#### Step 4 — Configure your site

```yaml
search_console:
  credentials_file: "client_secret_xxx.json"
  token_file: "gsc_token.json"
  site_url: "https://yoursite.com/"        # must match GSC exactly
  protection_thresholds:
    min_clicks: 10
    min_impressions: 100
    max_position: 20.0
```

#### Step 5 — Authorize

Open the **Analytics** tab → click **Connect GSC**. Sign in with your Google account. The token is saved to `gsc_token.json` automatically.

---

## Pipeline Modes

| Mode | Description |
|---|---|
| `new` | Research keywords → generate a new blog post with images |
| `update` | Find underperforming posts via GSC → rewrite them |
| `full` | New post + updates + static pages in one run |
| `static` | Rewrite static pages (homepage, about, etc.) |
| `images` | Scan all posts, check image quality, generate/replace as needed |
| `recover` | Restore posts that lost rankings after an update |
| `diagnose` | Deep SEO audit: indexing, Core Web Vitals, cannibalization |
| `dedupe` | Detect and fix keyword cannibalization |
| `impact` | Measure GSC traffic impact of recent updates (before vs after) |
| `products` | Rewrite WooCommerce/Shopify product pages |
| `restore_titles` | Restore original URL slugs from update history |

Run from the UI (Pipelines tab) or CLI:

```bash
python run.py new --config config.mysite.yaml
python run.py update --config config.mysite.yaml
```

---

## CLI Usage

```bash
python run.py new                            # uses config.yaml (default)
python run.py new --config config.mysite.yaml
python run.py update --config config.mysite.yaml
python run.py full --config config.mysite.yaml
```

---

## Docker

```bash
# Start everything
docker compose up

# UI still runs locally:
cd ui && npm install && npm run dev
```

The API is available at `http://localhost:8000` and the UI at `http://localhost:5173`.

> Config files are mounted from the host — edit them on your machine as normal.

---

## Project Structure

```
seo-blog-engine/
├── run.py                     # CLI entry point
├── orchestrator.py            # Main pipeline logic (all 11 modes)
├── config.example.*.yaml      # Config templates per platform
│
├── api/                       # FastAPI backend
│   ├── main.py                # lifespan: init_db, load schedules, start APScheduler
│   ├── config_manager.py
│   ├── db.py                  # SQLite init (pipeline_runs, pending_reviews, schedules, schedule_runs)
│   ├── scheduler.py           # APScheduler wrapper
│   └── routes/                # sites, pipelines, gsc, posts, products, history, reviews, schedules
│
├── publishers/                # Platform publisher abstraction
│   ├── base.py                # Abstract interface
│   ├── factory.py             # get_publisher(config)
│   └── mongodb.py / wordpress.py / woocommerce.py / shopify.py / wix.py
│
├── tools/                     # Research & analysis
│   ├── search_console.py      # GSC auth, performance, opportunities
│   ├── serp_scraper.py        # Google SERP scraping
│   ├── competitor_analyzer.py
│   └── blog_analyzer.py
│
├── generator/                 # AI content generation
│   ├── gemini_client.py
│   ├── prompts.py
│   └── refine.py              # AI chat refinement for review gate
│
├── publisher/                 # MongoDB publishing pipeline (blog-poster)
│   ├── post_publisher.py
│   ├── mongodb_client.py
│   ├── supabase_client.py
│   └── tiptap_converter.py
│
├── ui/                        # Vue 3 + Vite frontend
│   └── src/
│       ├── views/             # Dashboard, Sites, Pipelines, Analytics, Posts, Products, History,
│       │                      #   Schedules, PostReview
│       ├── components/        # AppSidebar, LiveLog, TipTapEditor, AddSiteWizard, wizard/*, ui/*
│       ├── stores/            # Pinia: sites, pipelines, wizard, reviews, schedules
│       └── i18n/              # English + Hebrew translations
│
├── scheduled/                 # Gitignored — schedule logs and user bat/sh files
│   └── logs/                  # {site}-{mode}.log per schedule run
│
├── Dockerfile
├── docker-compose.yml
└── start.sh                   # One-command local startup
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 + TypeScript + Vite + TailwindCSS |
| UI style | shadcn/ui pattern (CSS variables, orange primary) |
| Rich text editor | TipTap (`@tiptap/vue-3`, starter-kit, extensions) |
| Charts | Chart.js + vue-chartjs |
| State | Pinia |
| i18n | vue-i18n (English + Hebrew) |
| Backend | FastAPI + uvicorn |
| Streaming | Server-Sent Events (SSE) |
| Scheduling | APScheduler (`apscheduler>=3.10.0`) |
| Pipeline history | SQLite |
| Config | YAML files per site (gitignored) |
| AI text | Gemini / OpenAI / Claude / Mistral / DeepSeek |
| AI images | Imagen 4 / DALL-E 3 |
| GSC | Google Search Console API v1 (OAuth2 Desktop) |
| Content DB | MongoDB Atlas (blog-poster platform) |
| Image storage | Supabase Storage (blog-poster platform) |

### Install notes

After cloning, the `start.sh` script handles all dependencies automatically. If installing manually:

```bash
pip install -r requirements.txt -r api/requirements.txt   # includes apscheduler
cd ui && npm install                                       # includes TipTap packages
```

---

## Documentation

Full technical documentation for contributors: [DOCS.md](DOCS.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev environment setup and PR guidelines.

## License

MIT — see [LICENSE](LICENSE).
