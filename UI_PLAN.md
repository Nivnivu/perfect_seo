# SEO Blog Engine — Open Source UI Build Plan

> Track progress here. Mark each phase ✅ when complete.

---

## ✅ Phase 1 — Foundation (DONE)

**Goal:** Working skeleton — API + Vue UI + SSE pipeline streaming

### Built:
- `api/` — FastAPI backend
  - `main.py` — app + CORS
  - `config_manager.py` — reads/writes all `config.*.yaml` files
  - `routes/sites.py` — GET/POST/PUT/DELETE /api/sites
  - `routes/pipelines.py` — POST /api/pipelines/run → SSE stream of subprocess stdout
  - `routes/history.py` — GET /api/history/{site} + /recovery
  - `requirements.txt` — fastapi, uvicorn, sse-starlette, pyyaml
- `ui/` — Vue 3 + Vite + TypeScript + Tailwind + shadcn-style
  - Bright design: dark sidebar (#0f172a), white content, orange primary
  - CSS variables following shadcn/ui spec
  - shadcn components: Button, Card, Badge, Input, Label, Separator
  - Pinia stores: `sites.ts`, `pipelines.ts`
  - Views: Dashboard (site cards), Sites (list), Pipelines (live log), History
  - LiveLog component with color-coded SSE terminal output
- `start.sh` — one-command startup for Git Bash (auto-kills stale port 8000)
- `start.bat` — Windows CMD version

### How to run:
```bash
./start.sh
# API: http://localhost:8000  |  UI: http://localhost:5173
```

---

## ✅ Phase 2 — Site Config Wizard (DONE)

**Goal:** Multi-step "Add Site" wizard modal — users can configure any new site through the UI

### Files created/modified:

#### API
- [x] `api/models/site.py` — added `TestConnectionRequest` model
- [x] `api/routes/sites.py` — added `POST /api/sites/test-connection` endpoint
  - MongoDB: pymongo ping (5s timeout)
  - WordPress: GET /wp-json/wp/v2/users/me with BasicAuth
  - WooCommerce: GET /wp-json/wc/v3/system_status with consumer key
  - Shopify: GET /admin/api/2024-01/shop.json with access token
  - Wix: return "validated at runtime" (no test needed)

#### UI — new shadcn primitives
- [x] `ui/src/components/ui/Textarea.vue`
- [x] `ui/src/components/ui/Alert.vue` (variants: success/error/warning/info)

#### UI — wizard store
- [x] `ui/src/stores/wizard.ts`
  - `isOpen`, `currentStep`, `saving`, `saveError`
  - `form` reactive object (all fields for all steps, flat structure)
  - `validateStep(step)` → string | null
  - `buildConfig()` → YAML-compatible dict
  - `save()` → POST /api/sites, then refresh sites store + site_id collision check

#### UI — wizard step components (ui/src/components/wizard/)
- [x] `StepPlatform.vue` — visual cards: MongoDB / WordPress / WooCommerce / Shopify / Wix
- [x] `StepSiteInfo.vue` — site_id (auto-derived + sanitized), name, domain, blog_url, language, country, Gemini key + model
- [x] `StepCredentials.vue` — dynamic fields per platform + inline "Test Connection" button with live result
- [x] `StepSearchConsole.vue` — enable toggle, credentials file, site URL, protection thresholds, setup guide
- [x] `StepContent.vue` — seed keywords, competitors, brand voice, image style, USPs (all optional)
- [x] `StepReview.vue` — read-only summary with masked secrets + Save button

#### UI — wizard container
- [x] `ui/src/components/AddSiteWizard.vue`
  - `<Teleport to="body">` modal overlay with backdrop-blur
  - Dark left sidebar: numbered steps (completed ✓ / active / pending), click to navigate back
  - Right: `<component :is="currentComponent" />` with scroll
  - Footer: Back | Next / Save Site with validation error display
  - Dirty-check confirm on close, slide+fade transition

#### UI — wired up
- [x] `ui/src/views/Sites.vue` — "Add Site" button opens wizard, empty state also prompts wizard

### Design notes:
- Modal: `max-w-4xl`, `h-[80vh]`, `Teleport to="body"`, `backdrop-blur-sm`
- Sidebar: dark (`bg-sidebar`), same as app sidebar
- Completed step: orange circle + white checkmark
- Active step: orange border + orange number
- Pending step: gray border + gray number
- Clicking a completed step navigates back to it

### Wizard form structure (what buildConfig() produces → YAML):
```yaml
platform: mongodb
gemini:
  api_key: ...
  model: gemini-2.5-flash
  image_model: imagen-4.0-fast-generate-001
site:
  name: ...
  domain: ...
  blog_url: ...
  language: en
  country: us
  google_domain: google.com
scraping:
  user_agent: "Mozilla/5.0..."
  request_delay: 2
mongodb:               # OR wordpress/shopify/wix block
  uri: ...
  database: multiBlogDB
  collection: ...
supabase:              # for mongodb + wordpress
  url: ...
  key: ...
  bucket: blog-poster
search_console:        # optional
  credentials_file: ...
  token_file: gsc_token.json
  site_url: ...
  protection_thresholds:
    min_clicks: 10
    min_impressions: 100
    max_position: 20.0
keywords:
  seeds: [...]
competitors: [...]
context:
  brand_voice: ...
  image_style:
    description: ...
    visual_elements: ...
    color_palette: ...
  unique_selling_points: [...]
```

---

## ✅ Phase 3 — Pipeline Runner + Live Log Polish (DONE)

**Goal:** Full-featured pipeline execution UX

### Built:
- [x] `api/db.py` — SQLite setup (`pipeline_runs` table)
- [x] `api/routes/pipelines.py` — Updated:
  - `POST /api/pipelines/run` — creates DB record first, emits `__RUN_ID__{id}` as first SSE event, stores process in `_active_runs` dict, saves log tail + exit_code on finish
  - `DELETE /api/pipelines/run/{run_id}` — terminates process, marks exit_code=-1 in DB
  - `GET /api/pipelines/history?site_id=&limit=` — returns recent runs from SQLite
- [x] `ui/src/stores/pipelines.ts` — Added: `runId`, `history`, `abort()`, `downloadLog()` (client-side Blob), `fetchHistory()`
- [x] `ui/src/views/Pipelines.vue` — Added: Abort button (replaces Run when running), Download log button, Recent Runs history table (mode badge, duration, status badge, log preview)
- [x] `start.sh` — Auto-opens browser at `http://localhost:5173` after 3s delay

### AI Provider support (added before Phase 3):
- [x] `ui/src/stores/wizard.ts` — Replaced `gemini_api_key`/`gemini_model` with `ai_provider`/`ai_api_key`/`ai_model`/`ai_image_model`; `buildConfig()` outputs provider-keyed block
- [x] `ui/src/components/wizard/StepSiteInfo.vue` — Full provider selector (5 cards: Gemini, OpenAI, Claude, Mistral, DeepSeek), dynamic model dropdown per provider, image model selector for Gemini/OpenAI
- [x] `ui/src/components/wizard/StepReview.vue` — Updated to show provider name, model, masked API key, image model

---

## ✅ Phase 4 — Platform Publishers (DONE)

**Goal:** Real publishing to WordPress, WooCommerce, Shopify, Wix

### Built:
- [x] `publishers/__init__.py`
- [x] `publishers/base.py` — `BasePlatformPublisher` abstract class (`fetch_posts`, `publish_post`, `update_post`, `test_connection`)
- [x] `publishers/mongodb.py` — wraps `publisher/post_publisher.py` + `mongodb_client.py`
- [x] `publishers/wordpress.py` — WP REST API v2 (BasicAuth)
- [x] `publishers/woocommerce.py` — WooCommerce REST API v3 (consumer key/secret)
- [x] `publishers/shopify.py` — Shopify Admin API 2024-01 (access token)
- [x] `publishers/wix.py` — Wix Blog v3 API
- [x] `publishers/factory.py` — `get_publisher(config)` returns correct publisher by `config["platform"]`

---

## ✅ Phase 5 — Dashboard & Analytics (DONE)

**Goal:** GSC data visualization and post management

### Built:
- [x] `api/routes/gsc.py` — `GET /api/gsc/{site_id}?days=` (summary + top pages + opportunities) + `GET /api/gsc/{site_id}/series?weeks=` (weekly trend chart data); graceful handling when GSC not configured / token missing
- [x] `api/routes/posts.py` — `GET /api/posts/{site_id}?limit=` via publishers factory
- [x] `api/main.py` — registers gsc + posts routers
- [x] `ui/src/views/Analytics.vue` — site selector, time-range selector, 4 KPI cards (clicks/impressions/position/CTR), line chart (clicks+impressions over time, dual Y-axis), bar chart (top 10 pages by clicks), Opportunities tabs (page2 / low CTR), full top pages table
- [x] `ui/src/views/Posts.vue` — site selector, search filter, posts table (thumbnail, title, excerpt, status badge, date, open link); platform-agnostic (MongoDB/WP/Shopify/Wix/WC)
- [x] `ui/package.json` — added `chart.js ^4.4.0` + `vue-chartjs ^5.3.0`
- [x] Router + sidebar updated with Analytics + Posts nav items
- [x] `start.sh` — always runs `npm install` to pick up new deps

---

## ✅ Phase 6 — Open Source Polish (DONE)

**Goal:** Ready for public release on GitHub

### Built:
- [x] `README.md` — full setup guide: Quick Start, all 5 platforms, all 5 AI providers, GSC OAuth (5-step), pipeline modes, CLI, Docker, project structure, tech stack
- [x] `config.example.yaml` — updated with `platform:` field and multi-provider format
- [x] `config.example.mongodb.yaml` — MongoDB + Supabase template
- [x] `config.example.wordpress.yaml` — WordPress REST API template
- [x] `config.example.woocommerce.yaml` — WooCommerce REST API template
- [x] `config.example.shopify.yaml` — Shopify Admin API template
- [x] `config.example.wix.yaml` — Wix Blog v3 API template
- [x] `Dockerfile` — Python 3.11-slim, installs both requirements files, exposes 8000
- [x] `docker-compose.yml` — API container with host config mount; optional MongoDB service (commented out)
- [x] `.github/workflows/ci.yml` — GitHub Actions: ruff lint (Python) + Vue build (Node 18)
- [x] `CONTRIBUTING.md` — dev setup, project layout, how to add platforms/providers, code style (ruff), PR guidelines
- [x] `LICENSE` — MIT
- [x] `.gitignore` — added: `client_secret_*.json`, `gsc_token.json`, `*.db`, `ui/dist/`, `!config.example.*.yaml`
- [x] `api/requirements.txt` — added `requests>=2.31.0` (used by WP/WC/Shopify/Wix publishers)

---

## Architecture Reference

```
seo-blog-engine/
├── orchestrator.py          # Existing Python engine
├── run.py                   # Existing CLI
├── api/                     # FastAPI backend (Phase 1)
│   ├── main.py
│   ├── config_manager.py
│   ├── models/
│   └── routes/
├── publishers/              # Multi-platform publishers (Phase 4)
│   ├── base.py
│   ├── mongodb.py
│   ├── wordpress.py
│   ├── woocommerce.py
│   ├── shopify.py
│   └── wix.py
├── ui/                      # Vue 3 frontend (Phase 1+)
│   └── src/
│       ├── views/
│       ├── components/
│       │   ├── ui/          # shadcn components
│       │   └── wizard/      # Phase 2 wizard steps
│       └── stores/
├── start.sh                 # Git Bash startup
└── start.bat                # Windows CMD startup
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 + TypeScript + Vite |
| UI Library | shadcn-vue (bright orange theme) |
| State | Pinia |
| Charts | Chart.js + vue-chartjs (Phase 5) |
| Backend | FastAPI (Python) |
| Streaming | Server-Sent Events (SSE) |
| Config | YAML files (per site) |
