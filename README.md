# SEO Blog Engine

An AI-powered SEO content engine with a **local web UI**. Research keywords, generate optimized blog posts with images, update underperforming content using Google Search Console data, and publish directly to your CMS — all from a clean browser interface.

Works with **any AI provider** and **any major CMS platform**.

---

## Features

- **Local web UI** — no SaaS, no subscriptions, runs on your machine
- **Multi-platform** — MongoDB, WordPress, WooCommerce, Shopify, Wix
- **Any AI provider** — Google Gemini, OpenAI, Anthropic Claude, Mistral, DeepSeek
- **GSC integration** — protect ranking pages, find page-2 opportunities, track performance
- **Live pipeline streaming** — watch every step in real time, abort anytime, download logs
- **Multi-site** — manage unlimited sites from one UI, each with its own config
- **Pipeline history** — every run logged with status, duration, and log preview

---

## Quick Start

> **Requirements:** Python 3.10+, Node.js 18+, Git Bash (Windows) or any Unix shell

```bash
git clone https://github.com/your-username/seo-blog-engine.git
cd seo-blog-engine
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
# Choose the one that matches your platform:
cp config.example.mongodb.yaml   config.mysite.yaml
cp config.example.wordpress.yaml config.mysite.yaml
cp config.example.shopify.yaml   config.mysite.yaml
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
  model: "gpt-4o"
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

#### MongoDB (default)

You need a MongoDB Atlas cluster and a Supabase project for image storage.

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

**MongoDB Atlas:** Create a free cluster at [mongodb.com/atlas](https://www.mongodb.com/atlas) → Database → Connect → Drivers → copy the URI.

**Supabase:** Create a project at [supabase.com](https://supabase.com) → Settings → API → copy URL and service_role key. Create a storage bucket named `blog-poster` and set it to public.

---

#### WordPress

Uses the WordPress REST API v2 with an Application Password (no plugins needed).

```yaml
platform: wordpress

wordpress:
  site_url: "https://yourblog.com"
  username: "your-wp-username"
  app_password: "xxxx xxxx xxxx xxxx xxxx xxxx"  # WP Admin → Users → Edit → Application Passwords
```

**How to get an Application Password:**
1. Go to WordPress Admin → Users → Edit your user
2. Scroll to **Application Passwords** section
3. Enter a name (e.g. "SEO Engine") → click **Add New Application Password**
4. Copy the generated password (shown only once)

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
1. Go to WooCommerce → Settings → Advanced → REST API
2. Click **Add Key** → set permissions to **Read/Write**
3. Copy the Consumer Key and Consumer Secret

---

#### Shopify

```yaml
platform: shopify

shopify:
  store_domain: "your-store.myshopify.com"
  admin_api_token: "shpat_..."
```

**How to get an Admin API token:**
1. Shopify Admin → Settings → Apps and sales channels → Develop apps
2. Enable custom app development → Create an app
3. Configure Admin API scopes: `read_content`, `write_content`, `read_products`, `write_products`
4. Install the app → copy the Admin API access token

---

#### Wix

```yaml
platform: wix

wix:
  api_key: "IST.eyJ..."                     # Wix API key (starts with IST.)
  site_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

**How to get Wix credentials:**
1. Go to [Wix Dev Center](https://dev.wix.com) → API Keys
2. Create a key with **Blog** and **Stores** permissions
3. Your site ID is in your Wix dashboard URL

---

### 4. Google Search Console (optional but recommended)

GSC enables: ranking protection (never overwrite pages with real clicks), page-2 opportunity detection, CTR optimization, and the Analytics dashboard.

**Each user needs their own Google Cloud credentials — do not share yours.**

#### Step 1 — Create a Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g. "SEO Blog Engine")
3. Go to **APIs & Services → Library** → search **Google Search Console API** → Enable it

#### Step 2 — Create OAuth credentials

1. Go to **APIs & Services → Credentials** → **Create Credentials → OAuth 2.0 Client ID**
2. Application type: **Desktop app**
3. Name it anything (e.g. "SEO Engine Local")
4. Download the JSON → save it to the project root as `client_secret_xxx.json`

#### Step 3 — OAuth consent screen (for your own use)

1. Go to **APIs & Services → OAuth consent screen**
2. User type: **External** → fill in App name + your email
3. Add scope: `https://www.googleapis.com/auth/webmasters.readonly`
4. Add yourself as a **Test user** (under "Test users")
5. Keep the app in **Testing** mode — you do NOT need to publish it for personal/team use

> **Why keep it in Testing mode?** Publishing requires a Google security review. Since this is a local tool using your own credentials accessing your own Search Console data, Testing mode is correct. Every user of the open-source project creates their own project + stays in Testing mode.

#### Step 4 — Configure your site

```yaml
search_console:
  credentials_file: "client_secret_xxx.json"   # path relative to project root
  token_file: "gsc_token.json"                  # auto-saved after first auth
  site_url: "https://yoursite.com/"             # must match exactly what's in GSC
  protection_thresholds:
    min_clicks: 10        # pages with more clicks than this are NEVER rewritten
    min_impressions: 100
    max_position: 20.0
```

#### Step 5 — Authorize in the browser

Open the **Analytics** tab in the UI → click **Connect GSC**. Your browser will open Google's authorization page. Sign in with the Google account that has Search Console access. The token is saved to `gsc_token.json` and reused automatically.

---

## Pipeline Modes

| Mode | Description |
|---|---|
| `new` | Research keywords → generate a new blog post with images |
| `update` | Find underperforming posts via GSC → rewrite them |
| `full` | New post + updates + static pages in one run |
| `static` | Rewrite static pages (homepage, about, etc.) |
| `images` | Generate missing images for existing posts |
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
# All modes support --config to target a specific site
python run.py new                          # uses config.yaml (default)
python run.py new --config config.pawly.yaml
python run.py update --config config.everst.yaml
python run.py full --config config.shop.yaml
```

---

## Docker

Run the API in a container while keeping the UI local:

```bash
# Start everything
docker compose up

# UI still runs locally (in a separate terminal):
cd ui && npm install && npm run dev
```

Or run only the API in Docker and the UI locally:

```bash
docker compose up api
cd ui && npm install && npm run dev
```

The API is available at `http://localhost:8000` and the UI at `http://localhost:5173`.

> **Config files** are mounted from the host — edit them on your machine as normal.

---

## Project Structure

```
seo-blog-engine/
├── run.py                     # CLI entry point
├── orchestrator.py            # Main pipeline logic
├── config.example.*.yaml      # Config templates per platform
│
├── api/                       # FastAPI backend (local web server)
│   ├── main.py
│   ├── config_manager.py
│   └── routes/                # sites, pipelines, gsc, posts, history
│
├── publishers/                # Multi-platform publisher abstraction
│   ├── base.py                # Abstract interface
│   ├── mongodb.py / wordpress.py / woocommerce.py / shopify.py / wix.py
│   └── factory.py             # get_publisher(config)
│
├── tools/                     # Research & analysis
│   ├── search_console.py      # GSC auth, performance, opportunities
│   ├── serp_scraper.py        # Google SERP scraping
│   ├── competitor_analyzer.py
│   └── blog_analyzer.py
│
├── generator/                 # AI content generation
│   ├── gemini_client.py
│   └── prompts.py
│
├── publisher/                 # MongoDB publishing pipeline
│   ├── post_publisher.py
│   ├── mongodb_client.py
│   ├── supabase_client.py
│   └── tiptap_converter.py
│
├── ui/                        # Vue 3 + Vite frontend
│   └── src/
│       ├── views/             # Dashboard, Sites, Pipelines, Analytics, Posts, History
│       ├── components/        # AppSidebar, LiveLog, AddSiteWizard, ui/*
│       └── stores/            # Pinia: sites, pipelines, wizard
│
├── Dockerfile                 # API container
├── docker-compose.yml
└── start.sh                   # One-command local startup
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 + TypeScript + Vite + TailwindCSS |
| UI Style | shadcn/ui pattern (CSS variables, orange primary) |
| Charts | Chart.js + vue-chartjs |
| State | Pinia |
| Backend | FastAPI + uvicorn |
| Streaming | Server-Sent Events (SSE) |
| Pipeline history | SQLite |
| Config | YAML files (per site, gitignored) |
| AI text | Gemini / OpenAI / Claude / Mistral / DeepSeek |
| AI images | Imagen 4 / DALL-E 3 |
| GSC | Google Search Console API v1 (OAuth2 Desktop) |
| Content DB | MongoDB Atlas |
| Image storage | Supabase Storage |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up a dev environment and submit changes.

---

## License

MIT — see [LICENSE](LICENSE).
