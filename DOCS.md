# SEO Blog Engine — Developer Documentation

This document is the technical reference for contributors and anyone extending the project. For setup and usage, see [README.md](README.md).

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Backend — FastAPI](#2-backend--fastapi)
3. [Publisher System](#3-publisher-system)
4. [Pipeline Engine (orchestrator.py)](#4-pipeline-engine-orchestratorpy)
5. [GSC Integration](#5-gsc-integration)
6. [Config System](#6-config-system)
7. [Frontend — Vue 3](#7-frontend--vue-3)
8. [UI Views Reference](#8-ui-views-reference)
9. [Wizard (Add Site)](#9-wizard-add-site)
10. [Manual Review Gate](#10-manual-review-gate)
11. [Scheduled Automation](#11-scheduled-automation)
12. [Data Schemas](#12-data-schemas)
13. [How To: Add a New Platform](#13-how-to-add-a-new-platform)
14. [How To: Add a New AI Provider](#14-how-to-add-a-new-ai-provider)
15. [How To: Add a New Pipeline Mode](#15-how-to-add-a-new-pipeline-mode)
16. [How To: Add a New UI Page](#16-how-to-add-a-new-ui-page)
17. [Environment & Dev Workflow](#17-environment--dev-workflow)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser  (http://localhost:5173)                           │
│  Vue 3 + Pinia + vue-i18n + Chart.js + TipTap              │
│                                                             │
│  Pages: Dashboard · Sites · Pipelines · Analytics          │
│          Posts · Products · History · Reviews · Schedules  │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP / SSE
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI  (http://localhost:8000)                           │
│  api/main.py + api/routes/*.py                              │
│                                                             │
│  /api/sites        CRUD for config YAML files               │
│  /api/pipelines    launch + stream (SSE) pipeline runs      │
│  /api/posts        fetch posts per site                     │
│  /api/products     fetch products per site                  │
│  /api/gsc          GSC auth + analytics                     │
│  /api/history      SQLite pipeline run log                  │
│  /api/reviews      pending review queue (Manual Review Gate)│
│  /api/schedules    cron schedule CRUD + run history         │
└──────┬───────────────────────────────┬──────────────────────┘
       │                              │
       ▼                              ▼
┌─────────────────┐        ┌──────────────────────────────────┐
│  Config YAML    │        │  orchestrator.py                 │
│  (per site)     │        │  11 pipeline modes               │
│  api/           │        │  spawned in asyncio.to_thread    │
│  config_manager │        └──────────────┬───────────────────┘
└─────────────────┘                       │
                                          │ uses
                          ┌───────────────┼──────────────────┐
                          ▼               ▼                  ▼
               ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
               │  publishers/ │  │   tools/     │  │  generator/  │
               │  (CMS layer) │  │  (research)  │  │  (AI calls)  │
               └──────┬───────┘  └──────────────┘  └──────────────┘
                      │
          ┌───────────┼──────────────┐──────────────┐
          ▼           ▼              ▼               ▼
     WordPress   WooCommerce      Shopify          Wix
     REST API    REST API         Admin API        Blog v3 API
                                                   (+ MongoDB)
```

### Key design principles

- **No shared mutable state between pipeline runs** — each run is a fresh subprocess via `asyncio.to_thread`
- **Config files are the source of truth** — no database for site config, just YAML files in the project root
- **Publisher abstraction** — all CMS interactions go through `BasePlatformPublisher`; the orchestrator never calls CMS APIs directly
- **SSE for streaming** — pipeline logs stream to the browser via Server-Sent Events; the frontend never polls
- **GSC protection is mandatory** — if GSC is configured but fails to fetch, updates are blocked entirely
- **Review gate is opt-in** — pipelines publish directly by default; enabling "Manual review" routes output to the `pending_reviews` table instead

---

## 2. Backend — FastAPI

### Entry point: `api/main.py`

The app uses a FastAPI `lifespan` context manager:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()          # create SQLite tables if not present
    load_all()         # load persisted schedules from DB into APScheduler
    scheduler.start()  # start background scheduler
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", ...])

app.include_router(sites.router,     prefix="/api/sites")
app.include_router(pipelines.router, prefix="/api/pipelines")
app.include_router(history.router,   prefix="/api/history")
app.include_router(gsc.router,       prefix="/api/gsc")
app.include_router(posts.router,     prefix="/api/posts")
app.include_router(products.router,  prefix="/api/products")
app.include_router(reviews.router,   prefix="/api/reviews")
app.include_router(schedules.router, prefix="/api/schedules")
```

### Route reference

#### `api/routes/sites.py`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/sites` | List all configured sites (from YAML files) |
| `GET` | `/api/sites/{site_id}` | Get full config for one site |
| `POST` | `/api/sites` | Create site — writes `config.{site_id}.yaml` |
| `PUT` | `/api/sites/{site_id}` | Update site config |
| `DELETE` | `/api/sites/{site_id}` | Delete config file |
| `POST` | `/api/sites/{site_id}/test` | Test platform connection |

`POST /api/sites` payload:
```json
{
  "site_id": "mysite",
  "platform": "wordpress",
  "config": { /* full YAML-equivalent dict */ }
}
```

#### `api/routes/pipelines.py`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/pipelines/modes` | List available pipeline modes |
| `POST` | `/api/pipelines/run` | Start a pipeline run → returns SSE stream |
| `POST` | `/api/pipelines/{run_id}/abort` | Abort a running pipeline |

The `/run` endpoint returns `text/event-stream`. Each event is a JSON line:
```json
{"type": "log", "text": "Researching keywords..."}
{"type": "done", "exit_code": 0}
{"type": "error", "text": "..."}
```

#### `api/routes/gsc.py`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/gsc/{site_id}/status` | Check GSC auth status |
| `POST` | `/api/gsc/{site_id}/auth` | Start OAuth flow, return auth URL |
| `GET` | `/api/gsc/{site_id}/analytics` | Fetch GSC performance (clicks, impressions, position) |
| `GET` | `/api/gsc/{site_id}/pages` | All pages with stats as `{url: {clicks, impressions, position, ctr_pct}}` |

`/pages` is used by the Posts and Products views to populate the GSC hover tooltips without an additional per-row API call.

#### `api/routes/posts.py`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/posts/{site_id}` | Fetch posts via the site's publisher |

Query params: `limit` (default 50, max 200).

Returns an array of post objects. Fields guaranteed across all platforms:
```json
{
  "_id": "string",
  "title": "string",
  "subtitle": "string (may contain HTML)",
  "image1Url": "string (full URL or empty)",
  "url": "string (full URL or empty)",
  "created_at": "ISO string or empty",
  "status": "published | draft | unknown"
}
```

#### `api/routes/products.py`

Same contract as posts. Additional field:
```json
{ "price": "string (e.g. '29.99' or empty)" }
```

#### `api/routes/history.py`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/history` | List pipeline run history from SQLite |
| `GET` | `/api/history/{run_id}` | Get full log for one run |

#### `api/routes/reviews.py`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/reviews` | List all pending reviews |
| `GET` | `/api/reviews/{review_id}` | Get a single pending review (title, body, meta) |
| `PUT` | `/api/reviews/{review_id}` | Save edits to a pending review (title, subtitle, body) |
| `POST` | `/api/reviews/{review_id}/publish` | Publish review to the CMS and remove from queue |
| `DELETE` | `/api/reviews/{review_id}` | Discard a pending review |
| `POST` | `/api/reviews/{review_id}/refine` | Send a chat message to the AI; returns refined content |

#### `api/routes/schedules.py`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/schedules` | List all schedules |
| `POST` | `/api/schedules` | Create a new schedule |
| `PUT` | `/api/schedules/{schedule_id}` | Update schedule (timing, enabled state, etc.) |
| `DELETE` | `/api/schedules/{schedule_id}` | Delete a schedule |
| `GET` | `/api/schedules/{schedule_id}/runs` | List run history for one schedule |
| `GET` | `/api/schedules/{schedule_id}/runs/{run_id}/log` | Fetch log for one scheduled run |
| `POST` | `/api/schedules/{schedule_id}/toggle` | Enable or disable without deleting |

### Config manager: `api/config_manager.py`

| Function | Purpose |
|---|---|
| `list_sites()` | Summary info for all sites (reads all `config.*.yaml` in root) |
| `get_site(site_id)` | Full config dict for one site |
| `save_site(site_id, config_data)` | Write `config.{site_id}.yaml` |
| `delete_site(site_id)` | Delete config file |

Config files matching `config.example*.yaml` are excluded from the site list automatically.

---

## 3. Publisher System

### Interface: `publishers/base.py`

```python
class BasePlatformPublisher(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def fetch_posts(self, limit: int = 50) -> list[dict]: ...

    @abstractmethod
    def publish_post(self, post_data: dict) -> str:
        """Returns the new post's ID."""

    @abstractmethod
    def update_post(self, post_id: str, update_data: dict) -> bool: ...

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Returns (success, message)."""

    def fetch_products(self, limit: int = 50) -> list[dict]:
        """E-commerce only. Default returns []."""
        return []
```

### Factory: `publishers/factory.py`

```python
def get_publisher(config: dict) -> BasePlatformPublisher:
    platform = config.get("platform", "mongodb")
    match platform:
        case "wordpress":   return WordPressPublisher(config)
        case "woocommerce": return WooCommercePublisher(config)
        case "shopify":     return ShopifyPublisher(config)
        case "wix":         return WixPublisher(config)
        case _:             return MongoDBPublisher(config)
```

### Platform implementations

| File | Platform | Notes |
|---|---|---|
| `publishers/mongodb.py` | MongoDB + Supabase | Used by blog-poster CMS. Resolves bare Supabase filenames to full URLs. |
| `publishers/wordpress.py` | WordPress REST API v2 | Application password auth. Fetches posts from `/wp-json/wp/v2/posts`. |
| `publishers/woocommerce.py` | WooCommerce REST API v3 | Consumer key/secret auth. `fetch_products` uses `/wc/v3/products`. |
| `publishers/shopify.py` | Shopify Admin API 2024-01 | `X-Shopify-Access-Token` header. Fetches blog articles and products. |
| `publishers/wix.py` | Wix Blog API v3 | `Authorization: IST.xxx` header. Uses blog post drafts + publish flow. |

### Platform-aware content transform on publish

When a review is published via the Review Gate (`POST /api/reviews/{id}/publish`), the body is transformed to the target platform's native format:

- **MongoDB** → TipTap JSON via `html_to_tiptap_json()` in `publisher/tiptap_converter.py`
- **WordPress / WooCommerce / Shopify / Wix** → raw HTML (passed directly to the REST API)

### MongoDB-specific: image URL resolution

MongoDB stores bare filenames in `image1Url` (e.g. `"cover.webp"`). The publisher resolves these to full Supabase public URLs:

```
{supabase_url}/storage/v1/object/public/{bucket}/{upload_id}/{filename}
```

`upload_id` is resolved from `config.supabase.storage_user_id` → MongoDB `master_user` document → collection name (fallback chain).

### MongoDB-specific: post URL construction

Posts in the MongoDB CMS use the post title as the URL slug. The `blog_url` config field is the base:

```
url = f"{blog_url}/{title}"
```

Never use `sc-domain:` style GSC site URLs as a URL prefix — they are domain identifiers, not HTTP URLs.

---

## 4. Pipeline Engine (`orchestrator.py`)

### How the API runs pipelines

`api/routes/pipelines.py` spawns the orchestrator in a background thread:

```python
async def run_pipeline(site_id, mode, ...):
    config = get_site(site_id)
    proc = await asyncio.to_thread(orchestrator.run, config, mode, log_queue)
    # stream log_queue as SSE
```

### Pipeline modes

| Mode | Entry function | Description |
|---|---|---|
| `new` | `run_new_post_pipeline()` | SERP research → keyword → generate → publish (or queue for review) |
| `update` | `run_update_pipeline()` | GSC fetch → classify posts → rewrite low-performers |
| `full` | `run_full_pipeline()` | new + update + static in sequence |
| `static` | `run_static_pipeline()` | Rewrite static CMS pages |
| `images` | `run_images_pipeline()` | Scan all posts, check image quality (HTTP HEAD + PIL), generate/replace |
| `recover` | `run_recover_pipeline()` | Restore posts that lost rankings (from update history) |
| `diagnose` | `run_diagnose_pipeline()` | Indexing audit, Core Web Vitals, cannibalization check |
| `dedupe` | `run_dedupe_pipeline()` | Find and fix keyword-cannibalizing posts |
| `impact` | `run_impact_pipeline()` | Before/after GSC comparison for recent rewrites |
| `products` | `run_products_pipeline()` | Rewrite e-commerce product descriptions |
| `restore_titles` | `run_restore_titles_pipeline()` | Reset URL slugs from update history backup |

### GSC protection logic (update/full modes)

1. GSC is fetched at the start of each update run
2. If GSC is configured but **fails to fetch** → entire update is blocked (no silent fallback)
3. Posts are classified by GSC data:
   - `top_performer` (pos ≤ 10, clicks ≥ threshold) → **skipped entirely**
   - `page2_opportunity` (pos 11–30, impressions ≥ 20) → highest priority, full rewrite
   - `ctr_opportunity` (pos ≤ 10, CTR < 3%, impressions ≥ 50) → **subtitle only** (body untouched)
   - `low_performer` (impressions ≥ 5) → full rewrite
   - `not_indexed` (no GSC data) → full rewrite OK
4. Before any update, `preserve_title=original_title` is always passed to prevent URL slug changes

### Images pipeline (updated behavior)

The `images` mode no longer skips posts that already have images. It:

1. Scans **all** posts
2. Checks image quality via HTTP HEAD (file size) and optional PIL dimension check
3. Generates a single **1200×630** image per post (replacing the old desktop + mobile pair)
4. Downloads the original if one exists; generates a new image from the post description if missing or below quality threshold

### Update history

Every update is logged to `output/{collection}_update_history.json`:

```json
{
  "post_id": "...",
  "title": "...",
  "original_title": "...",
  "original_body": "...",
  "updated_at": "2026-03-27T...",
  "mode": "page2_opportunity",
  "gsc_protection": true
}
```

`original_body` is the pre-update TipTap JSON string. Used by `recover` mode to do full content restoration.

---

## 5. GSC Integration

### Auth flow

1. `GET /api/gsc/{site_id}/status` → checks if `gsc_token.json` exists and is valid
2. `POST /api/gsc/{site_id}/auth` → runs `tools/search_console.py:get_auth_url()` → returns Google OAuth URL
3. User completes OAuth in browser → callback saves token to `gsc_token.json`
4. All subsequent GSC calls use the saved token (auto-refreshed by the Google client library)

### Key functions in `tools/search_console.py`

| Function | Purpose |
|---|---|
| `fetch_gsc_performance(config, days)` | Returns `{url: {clicks, impressions, position, ctr_pct}}` for all pages |
| `classify_pages(perf_data, thresholds)` | Returns list of pages with their classification |
| `find_lost_pages(config)` | Cross-references recent updates with GSC drops |
| `match_post_to_gsc_url(title, url, gsc_data)` | Word-overlap matching for Hebrew/encoded URLs |

### URL matching (`match_post_to_gsc_url`)

Direct URL comparison often fails for Hebrew posts because:
- GSC stores percent-encoded URLs (`/blog/%D7%9B%D7%9C%D7%91`)
- The CMS stores the decoded title as the slug

The matcher decodes both sides and computes word overlap:

```python
score = overlap_count / min(title_word_count, slug_word_count)
# matched if score >= 0.4
```

The same logic is replicated in the frontend (`getGscStats()` in Posts.vue and Products.vue) to avoid an extra API call per row.

---

## 6. Config System

### File naming

| File | Site ID |
|---|---|
| `config.yaml` | `default` |
| `config.pawly.yaml` | `pawly` |
| `config.myshop.yaml` | `myshop` |
| `config.example*.yaml` | excluded from UI |

### Full config schema

```yaml
platform: wordpress          # mongodb | wordpress | woocommerce | shopify | wix

# --- AI provider (only one block) ---
gemini:
  api_key: "..."
  model: "gemini-2.5-flash"
  image_model: "imagen-4.0-fast-generate-001"   # optional

openai:
  api_key: "..."
  model: "gpt-4.1"
  image_model: "dall-e-3"                        # optional

anthropic:
  api_key: "..."
  model: "claude-sonnet-4-6"

mistral:
  api_key: "..."
  model: "mistral-large-latest"

deepseek:
  api_key: "..."
  model: "deepseek-chat"

# --- Site info ---
site:
  name: "My Blog"
  domain: "myblog.com"
  blog_url: "https://myblog.com/blog"
  language: "en"
  country: "us"
  google_domain: "google.com"
  logo: "companies_logos/mylogo.png"             # optional

# --- Scraping ---
scraping:
  user_agent: "Mozilla/5.0 ..."
  request_delay: 2

# --- Platform credentials (only the relevant block) ---
mongodb:
  uri: "mongodb+srv://..."
  database: "multiBlogDB"
  collection: "myblog"
  products_database: "myshop"                   # optional, for e-commerce

supabase:                                        # required for mongodb + wordpress
  url: "https://xxxx.supabase.co"
  key: "service-role-key"
  bucket: "blog-poster"

wordpress:
  site_url: "https://myblog.com"
  username: "admin"
  app_password: "xxxx xxxx xxxx xxxx xxxx xxxx"

woocommerce:
  site_url: "https://mystore.com"
  consumer_key: "ck_..."
  consumer_secret: "cs_..."

shopify:
  store_domain: "mystore.myshopify.com"
  admin_api_token: "shpat_..."

wix:
  api_key: "IST.eyJ..."
  site_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# --- Google Search Console (optional) ---
search_console:
  credentials_file: "client_secret_xxx.json"
  token_file: "gsc_token.json"
  site_url: "https://myblog.com/"               # or "sc-domain:myblog.com"
  protection_thresholds:
    min_clicks: 10
    min_impressions: 100
    max_position: 20.0

# --- Content context ---
keywords:
  seeds:
    - "keyword one"
    - "keyword two"

competitors:
  - "https://competitor.com/"

context:
  brand_voice: |
    Multi-line brand voice description.

  image_style:
    description: "A premium pet food brand."
    visual_elements: "Show happy pets with products."
    color_palette: "Warm earthy tones, browns, greens."

  unique_selling_points:
    - "Point one"
    - "Point two"

  urls:
    - url: "https://myblog.com"
      type: "homepage"
    - url: "https://myblog.com/products"
      type: "products"

  brands:
    - name: "Brand Name"
      description: "Brand description"
```

---

## 7. Frontend — Vue 3

### Stack

| Package | Role |
|---|---|
| Vue 3 + Composition API | UI framework |
| TypeScript | Type safety |
| Vite | Dev server + bundler |
| TailwindCSS | Utility CSS |
| Pinia | State management |
| vue-router | Client-side routing |
| vue-i18n | Internationalization |
| axios | HTTP client |
| lucide-vue-next | Icons |
| Chart.js + vue-chartjs | Analytics charts |
| @tiptap/vue-3 | Rich text editor core |
| @tiptap/starter-kit | Basic editor extensions |
| @tiptap/extension-link | Link support in editor |
| @tiptap/extension-placeholder | Placeholder text |
| @tiptap/extension-text-align | Text alignment controls |

### CSS variables (theme)

Defined in `ui/src/assets/main.css`. The primary color is orange (`--primary: hsl(25 95% 53%)`). Dark mode uses the same variables with different values. Changing the primary hue changes the entire theme.

### Stores (`ui/src/stores/`)

#### `sites.ts`
```typescript
useSitesStore() → {
  sites: Site[]           // loaded from GET /api/sites
  fetchSites()            // reload
  deleteSite(id)
}
```

#### `pipelines.ts`
```typescript
usePipelinesStore() → {
  runs: PipelineRun[]     // active + recent runs
  startRun(siteId, mode)  // POST /api/pipelines/run → opens SSE stream
  abortRun(runId)
  logs: Record<runId, string[]>
}
```

#### `wizard.ts`
```typescript
useWizardStore() → {
  isOpen: boolean
  currentStep: number     // 0–5
  form: WizardForm        // all field values
  validateStep(n)         // returns error string or null
  buildConfig()           // produces the API payload
  open() / close() / save()
}
```

#### `reviews.ts`
```typescript
useReviewsStore() → {
  pendingReviews: Review[]   // loaded from GET /api/reviews
  fetchReviews()
  publishReview(id)
  discardReview(id)
  refine(id, message)        // POST /api/reviews/{id}/refine → returns updated content
}
```

#### `schedules.ts`
```typescript
useSchedulesStore() → {
  schedules: Schedule[]      // loaded from GET /api/schedules
  fetchSchedules()
  createSchedule(payload)
  updateSchedule(id, payload)
  deleteSchedule(id)
  toggleSchedule(id)         // enable/disable
  fetchRuns(scheduleId)      // run history for one schedule
}
```

### i18n (`ui/src/i18n/`)

Translation files: `locales/en.json` and `locales/he.json`.

The app detects RTL from `document.dir` (set based on the active locale). Use `$t('key')` in templates and `useI18n().t('key')` in scripts.

When adding new UI text, add keys to both locale files.

---

## 8. UI Views Reference

| View | Route | API calls | Description |
|---|---|---|---|
| `Dashboard.vue` | `/` | `/api/sites`, `/api/history`, `/api/gsc/{id}/analytics` | Summary cards + traffic chart |
| `Sites.vue` | `/sites` | `/api/sites` CRUD | Site list + Add Site wizard |
| `Pipelines.vue` | `/pipelines` | `/api/pipelines/run` (SSE), `/api/reviews` | Run pipelines, live log, abort; shows "Content ready for review" banner when pending reviews exist |
| `Analytics.vue` | `/analytics` | `/api/gsc/{id}/analytics` | GSC performance charts |
| `Posts.vue` | `/posts` | `/api/posts/{id}`, `/api/gsc/{id}/pages` | Post table with GSC hover tooltip |
| `Products.vue` | `/products` | `/api/products/{id}`, `/api/gsc/{id}/pages` | Product table with price + GSC tooltip |
| `History.vue` | `/history` | `/api/history` | Pipeline run log |
| `PostReview.vue` | `/reviews/:id` | `/api/reviews/{id}`, `/api/reviews/{id}/refine` | TipTap editor + AI chat panel for reviewing and editing generated content before publishing |
| `Schedules.vue` | `/schedules` | `/api/schedules`, `/api/schedules/{id}/runs` | Create/edit/enable/disable cron schedules; per-schedule run history with log viewer |

### GSC hover tooltip pattern

Used in both Posts and Products. The pattern:

1. Load all GSC page stats once via `GET /api/gsc/{id}/pages` → `gscStats` ref
2. `getGscStats(item)` does word-overlap matching client-side (no extra requests per row)
3. On `mouseenter`, record `hoveredId` + calculate tooltip position from `getBoundingClientRect()`
4. Render tooltip via `<Teleport to="body">` with `position: fixed` to avoid overflow clipping

### Sidebar badge

The sidebar shows a **"Reviews (N)"** badge on the Reviews nav item when `pendingReviews.length > 0`. The count is polled or updated reactively via the reviews store.

---

## 9. Wizard (Add Site)

The wizard is a 6-step modal (`AddSiteWizard.vue` + `wizard/Step*.vue`).

| Step | Component | Validates |
|---|---|---|
| 0 | `StepPlatform.vue` | Platform selection (no required fields) |
| 1 | `StepSiteInfo.vue` | site_id, site_name, domain, AI key |
| 2 | `StepCredentials.vue` | Platform-specific fields |
| 3 | `StepSearchConsole.vue` | Optional — no blocking validation |
| 4 | `StepContent.vue` | Optional — seed keywords, brand voice |
| 5 | `StepReview.vue` | Shows YAML preview, calls `wizard.save()` |

`wizard.save()` calls `buildConfig()` → `POST /api/sites` → backend writes the YAML file → `sitesStore.fetchSites()` reloads the site list.

### Platform order in StepPlatform.vue

WordPress → WooCommerce → Shopify → Wix → MongoDB (blog-poster, last)

MongoDB is last because it requires external infrastructure (Atlas + Supabase) and is specifically for blog-poster CMS users.

---

## 10. Manual Review Gate

The review gate is an opt-in layer between content generation and publishing. When enabled on a pipeline run, generated posts are held in a queue for human review and editing before going live.

### Flow

1. User enables "Manual review" toggle in the Pipelines view before launching `new`, `update`, or `recover`
2. The orchestrator generates content normally but — instead of calling the publisher — writes it to the `pending_reviews` SQLite table
3. The Pipelines view shows a green **"Content ready for review"** banner
4. The sidebar **"Reviews (N)"** badge increments
5. User opens `/reviews/:id` — the `PostReview.vue` view — which shows:
   - Editable **title** and **meta description** fields
   - Full **TipTap rich-text editor** for body content
   - **AI chat refinement panel** on the right — type a prompt, get refined content back
6. User clicks **Publish** → `POST /api/reviews/{id}/publish` → content is transformed to the target platform's format and published via the normal publisher
7. User can also click **Discard** to delete the pending review without publishing

### TipTap Editor (`ui/src/components/TipTapEditor.vue`)

A reusable rich text editor component built on `@tiptap/vue-3`. Supports:

- **Bold**, **Italic**
- **H2**, **H3** headings
- **Bullet lists**, **Ordered lists**
- **Links** (insert/edit via toolbar)
- **Text alignment** (left, center, right)
- **Undo / Redo**

The editor emits `update:modelValue` (TipTap JSON) and accepts `v-model` in parent views.

### AI Refinement (`generator/refine.py`)

`POST /api/reviews/{id}/refine` accepts a `{ message: string }` body. The backend:

1. Loads the current pending review content
2. Builds a prompt combining the current body + the user's instruction
3. Calls the site's configured AI provider
4. Returns `{ title, subtitle, body }` with the refined content

The frontend updates the editor in place without saving — the user must still click Publish.

### Backend files

| File | Purpose |
|---|---|
| `api/routes/reviews.py` | All review CRUD + publish + refine endpoints |
| `api/db.py` | `pending_reviews` table definition and init |
| `generator/refine.py` | AI refinement prompt + provider dispatch |
| `ui/src/views/PostReview.vue` | Review/edit UI |
| `ui/src/components/TipTapEditor.vue` | Rich text editor component |
| `ui/src/stores/reviews.ts` | Pinia store for review state |

---

## 11. Scheduled Automation

Schedules allow pipeline modes to run automatically on a cron basis without manual intervention from the UI.

### How it works

- Schedules are stored in the `schedules` SQLite table (see [Data Schemas](#12-data-schemas))
- On API startup, `load_all()` in `api/scheduler.py` reads all enabled schedules from the DB and registers them with APScheduler
- APScheduler runs jobs in-process (no separate worker process needed)
- Each run is logged to `scheduled/logs/{site}-{mode}.log` and recorded in the `schedule_runs` table

### APScheduler integration (`api/scheduler.py`)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def load_all():
    """Load all enabled schedules from DB and add to scheduler."""
    for s in db.get_enabled_schedules():
        scheduler.add_job(
            run_scheduled_pipeline,
            trigger=CronTrigger.from_crontab(s["cron"]),
            id=s["id"],
            args=[s["site_id"], s["mode"]],
            replace_existing=True,
        )
```

### Schedule types

| Type | Cron expression | Example |
|---|---|---|
| Daily | `0 H * * *` | Every day at 08:00 |
| Weekly | `0 H * * D` | Every Monday at 06:00 |
| Monthly | `0 H 1 * *` | 1st of every month |
| Custom | Any valid cron | `0 */6 * * *` (every 6 hours) |

### Log files

Logs are written to `scheduled/logs/{site_id}-{mode}.log`. The `scheduled/` folder is gitignored — it contains user-specific automation scripts and logs that should not be committed.

### UI (`ui/src/views/Schedules.vue`)

- Lists all schedules with site, mode, cron expression, last run status, and next run time
- **Add schedule** form: pick site, mode, schedule type/cron, optional label
- Per-schedule **Enable / Disable** toggle (does not delete the schedule)
- **Run history** expandable panel per schedule, with a log viewer for each run
- **Delete** removes the schedule from both the DB and APScheduler

### Backend files

| File | Purpose |
|---|---|
| `api/routes/schedules.py` | Schedule CRUD + run history endpoints |
| `api/scheduler.py` | APScheduler wrapper, `load_all()`, `run_scheduled_pipeline()` |
| `api/db.py` | `schedules` and `schedule_runs` table definitions |
| `ui/src/views/Schedules.vue` | Schedules management UI |
| `ui/src/stores/schedules.ts` | Pinia store for schedule state |

### Dependency

`apscheduler>=3.10.0` is listed in `api/requirements.txt`.

---

## 12. Data Schemas

### SQLite tables (`pipeline_runs.db`)

#### `pipeline_runs`

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (UUID) | Run ID |
| `site_id` | TEXT | Site identifier |
| `mode` | TEXT | Pipeline mode |
| `status` | TEXT | `running` \| `completed` \| `failed` \| `aborted` |
| `started_at` | TEXT | ISO timestamp |
| `finished_at` | TEXT | ISO timestamp (null if running) |
| `duration_s` | REAL | Duration in seconds |
| `log` | TEXT | Full log output |
| `exit_code` | INTEGER | 0 = success |

#### `pending_reviews`

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (UUID) | Review ID |
| `site_id` | TEXT | Site identifier |
| `mode` | TEXT | Pipeline mode that generated it |
| `title` | TEXT | Post title |
| `subtitle` | TEXT | Meta description |
| `body` | TEXT | TipTap JSON or HTML depending on platform |
| `post_id` | TEXT | Existing post ID if this is an update (null for new posts) |
| `created_at` | TEXT | ISO timestamp |

#### `schedules`

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (UUID) | Schedule ID |
| `site_id` | TEXT | Site identifier |
| `mode` | TEXT | Pipeline mode to run |
| `cron` | TEXT | Cron expression (e.g. `0 8 * * 1`) |
| `label` | TEXT | Optional human-readable label |
| `enabled` | INTEGER | 1 = active, 0 = disabled |
| `created_at` | TEXT | ISO timestamp |
| `last_run_at` | TEXT | ISO timestamp of most recent run |
| `last_run_status` | TEXT | `completed` \| `failed` |

#### `schedule_runs`

| Column | Type | Description |
|---|---|---|
| `id` | TEXT (UUID) | Run ID |
| `schedule_id` | TEXT | FK → schedules.id |
| `started_at` | TEXT | ISO timestamp |
| `finished_at` | TEXT | ISO timestamp |
| `status` | TEXT | `completed` \| `failed` |
| `log` | TEXT | Full log output for this run |

### MongoDB post document (blog-poster CMS)

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Post ID |
| `title` | string | Post title (= URL slug) |
| `subtitle` | string | Meta description (may contain HTML) |
| `body` | string | TipTap JSON (stringified) |
| `image1Url` | string | Supabase filename or full URL |
| `image2Url` | string | Optional second image |
| `userId` | string | Supabase user ID |
| `blog` | string | Collection/blog identifier |
| `type` | string | `"blogPost"` or `"staticPage"` |
| `createdAt` | Date | Creation timestamp |

### TipTap JSON format

The blog-poster CMS uses TipTap as its rich text editor. Post bodies are stored as JSON strings. The `publisher/tiptap_converter.py` module converts Gemini markdown output to valid TipTap JSON. The `html_to_tiptap_json()` function in the same module is used when publishing from the Review Gate.

Static pages use a different schema: `{ type, content: [...] }` stored as a dict (not stringified).

---

## 13. How To: Add a New Platform

### Step 1 — Publisher class

Create `publishers/yourplatform.py`:

```python
from publishers.base import BasePlatformPublisher

class YourPlatformPublisher(BasePlatformPublisher):

    def fetch_posts(self, limit: int = 50) -> list[dict]:
        # Call your platform's API
        # Return list of dicts with keys:
        # _id, title, subtitle, image1Url, url, created_at, status
        ...

    def publish_post(self, post_data: dict) -> str:
        # post_data contains: gemini_output, desktop_image, mobile_image
        # Return the new post's ID as a string
        ...

    def update_post(self, post_id: str, update_data: dict) -> bool:
        # update_data may contain: title, subtitle, body
        # Return True if update succeeded
        ...

    def test_connection(self) -> tuple[bool, str]:
        # Return (True, "Connected") or (False, "error message")
        ...

    def fetch_products(self, limit: int = 50) -> list[dict]:
        # Optional — only for e-commerce platforms
        # Return list of dicts with keys:
        # _id, title, subtitle, image1Url, url, created_at, status, price
        ...
```

### Step 2 — Register in factory

In `publishers/factory.py`:

```python
case "yourplatform": return YourPlatformPublisher(config)
```

### Step 3 — UI: platform card

In `ui/src/components/wizard/StepPlatform.vue`, add to the `platforms` array:

```typescript
{
  id: 'yourplatform',
  label: 'Your Platform',
  icon: SomeIcon,            // from lucide-vue-next
  color: 'text-indigo-600',
  bg: 'bg-indigo-50',
  badge: null,
}
```

### Step 4 — UI: credential fields

In `ui/src/components/wizard/StepCredentials.vue`, add a `v-if` block:

```html
<template v-if="wizard.form.platform === 'yourplatform'">
  <div class="space-y-1.5">
    <Label>Site URL <span class="text-destructive">*</span></Label>
    <Input v-model="wizard.form.your_field" placeholder="https://..." />
  </div>
  <!-- more fields -->
</template>
```

Add the new fields to `defaultForm()` in `ui/src/stores/wizard.ts` and handle them in `buildConfig()` and `validateStep(2)`.

### Step 5 — Config example

Create `config.example.yourplatform.yaml` based on the existing examples.

### Step 6 — Update type union

In `ui/src/stores/wizard.ts`:

```typescript
platform: 'wordpress' as 'mongodb' | 'wordpress' | 'woocommerce' | 'shopify' | 'wix' | 'yourplatform'
```

---

## 14. How To: Add a New AI Provider

### Step 1 — Generator support

In `generator/gemini_client.py` (or a new file), add a client class for the provider. The orchestrator calls `generate_post(prompt, config)` — check how existing providers are dispatched there.

### Step 2 — UI: provider card + models

In `ui/src/components/wizard/StepSiteInfo.vue`, add to the `providers` array:

```typescript
{
  id: 'myprovider',
  name: 'My Provider',
  short: 'MyAI',
  keyPlaceholder: 'key-...',
  docsUrl: 'https://myprovider.com/api-keys',
  docsLabel: 'myprovider.com',
  models: [
    { id: 'myprovider-model-v1', label: 'My Model v1' },
    { id: 'myprovider-model-v2', label: 'My Model v2' },
  ],
  defaultModel: 'myprovider-model-v2',
  hasImageModel: false,
  imageModels: [],
  defaultImageModel: '',
}
```

### Step 3 — Store: type union + buildConfig

In `ui/src/stores/wizard.ts`, add `'myprovider'` to the `ai_provider` type union. The `buildConfig()` function already handles arbitrary providers with `config[form.ai_provider] = { api_key, model }`, so no change needed there unless your provider uses a different config key structure.

---

## 15. How To: Add a New Pipeline Mode

### Step 1 — Orchestrator function

In `orchestrator.py`, add a new function:

```python
def run_mymode_pipeline(config: dict, log) -> None:
    log("Starting my mode...")
    # your logic
```

Register it in the main dispatcher (look for the `match mode:` block).

### Step 2 — Expose in the API

In `api/routes/pipelines.py`, add `"mymode"` to the list of valid modes.

### Step 3 — UI

In `ui/src/views/Pipelines.vue`, add the mode to the mode selector with a label and description.

---

## 16. How To: Add a New UI Page

### Step 1 — View component

Create `ui/src/views/MyPage.vue`:

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSitesStore } from '@/stores/sites'
import axios from 'axios'

const sitesStore = useSitesStore()
const selectedSite = ref('')
const data = ref([])

onMounted(async () => {
  await sitesStore.fetchSites()
  if (sitesStore.sites.length > 0) {
    selectedSite.value = sitesStore.sites[0].id
    await loadData()
  }
})

async function loadData() {
  const res = await axios.get(`/api/myendpoint/${selectedSite.value}`)
  data.value = res.data
}
</script>

<template>
  <div class="p-8 max-w-6xl">
    <!-- your content -->
  </div>
</template>
```

### Step 2 — Router

In `ui/src/router/index.ts`:

```typescript
{ path: '/mypage', component: () => import('@/views/MyPage.vue') }
```

### Step 3 — Sidebar

In `ui/src/components/AppSidebar.vue`, add a nav item to the `navItems` array with the appropriate icon from `lucide-vue-next`.

### Step 4 — Backend route (if needed)

Create `api/routes/mypage.py`, register in `api/main.py`.

---

## 17. Environment & Dev Workflow

### Starting dev servers

```bash
./start.sh           # starts both API (port 8000) and UI (port 5173)
```

The API runs with `--reload` (auto-restarts on Python changes). The UI uses Vite HMR.

### Running only the API

```bash
pip install -r requirements.txt -r api/requirements.txt   # includes apscheduler
uvicorn api.main:app --reload --port 8000
```

### Running only the UI

```bash
cd ui
npm install          # includes TipTap packages
npm run dev          # http://localhost:5173
```

### Linting

```bash
# Python
pip install ruff
ruff check api/ publishers/ tools/ generator/ publisher/

# TypeScript/Vue (via Vite's type check)
cd ui && npm run type-check
```

### Building for production

```bash
cd ui && npm run build   # outputs to ui/dist/
```

The FastAPI app can serve the built UI statically — add `StaticFiles` mount in `api/main.py` pointing to `ui/dist/`.

### Adding translations

Edit `ui/src/i18n/locales/en.json` and `he.json`. Nest keys under the view/component name:

```json
{
  "myPage": {
    "title": "My Page",
    "subtitle": "Description here"
  }
}
```

Use `$t('myPage.title')` in templates.

### Docker build

```bash
docker build -t seo-blog-engine .
docker compose up
```

The `Dockerfile` installs both `requirements.txt` and `api/requirements.txt`, then starts uvicorn on port 8000. Config files are mounted as a volume at runtime.

---

## Questions or contributions?

Open an issue or PR at [github.com/Nivnivu/perfect_seo](https://github.com/Nivnivu/perfect_seo).
