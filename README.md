# Perfect SEO Blog Engine

An AI-powered, end-to-end SEO blog engine that researches keywords, analyzes competitors, generates optimized Hebrew blog posts with images, and publishes them — all with a human-in-the-loop WhatsApp approval flow.

## How It Works

```
Seed Keywords
     |
     v
[Phase 0] Scrape your own website for context (products, brand voice, internal links)
     |
[Phase 1] Expand keywords via Google Autocomplete + Google Trends
     |         10 seeds --> 100+ long-tail variations
     |
[Phase 2] Scrape Google SERPs for top keywords
     |         Extract: organic results, People Also Ask, related searches
     |         Analyze top competitor pages (headings, word count, keyword density)
     |
[Phase 3] Content gap analysis against your existing blog posts in MongoDB
     |         Find uncovered keywords with highest trend scores
     |
[Phase 4] Generate blog post with Gemini AI
     |         SEO-optimized, Hebrew, brand-aware, competitor-beating length
     |
[Phase 5] Generate desktop (4:3) + mobile (1:1) header images with Imagen
     |
[Phase 6] Send preview to WhatsApp for approval
     |         Owner can: approve / reject / send feedback for AI revision
     |
[Phase 7] Publish to MongoDB + upload images to Supabase
```

## Modes


  - Added recover mode: python run.py recover --config config.pawly.yaml 

| Command | Description |
|---|---|
| `python run.py new` | Research + generate + publish a single new blog post |
| `python run.py update` | Find and rewrite/expand underperforming existing posts |
| `python run.py static` | Rewrite static pages (homepage, registration, etc.) |
| `python run.py full` | Full run: new posts + updates + static pages |
| `python run.py images` | Generate images for posts that are missing them |

Use `--config` to target a specific site:

```bash
python run.py new --config config.pawly.yaml
python run.py update --config config.everst.yaml
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. WhatsApp module (optional, for approval flow)

```bash
cd whatsapp
npm install
```

On first run, a QR code will appear in the terminal — scan it with WhatsApp to authenticate. The session is saved for future runs.

### 3. Configure your site

Copy the example config and fill in your details:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with:
- **Gemini API key** — from [Google AI Studio](https://aistudio.google.com/)
- **MongoDB URI** — your MongoDB Atlas connection string
- **Supabase URL + key** — for image storage
- **Site details** — domain, language, competitors
- **Seed keywords** — 8-12 starting keywords for your niche
- **Brand context** — voice, USPs, products, image style

### 4. Run

```bash
python run.py new
```

## Config Structure

```yaml
gemini:
  api_key: "..."
  model: "gemini-2.5-flash"          # Text generation
  image_model: "imagen-4.0-fast-generate-001"  # Image generation (Imagen 4 Fast)

site:
  name: "YourBrand"
  domain: "yourbrand.com"
  blog_url: "https://yourbrand.com/blog"
  language: "he"                     # Content language
  country: "il"                      # Google Trends region
  google_domain: "google.co.il"      # SERP scraping domain

mongodb:
  uri: "mongodb+srv://..."
  database: "multiBlogDB"
  collection: "your_collection"

competitors:                         # Top 3-5 competitor websites
  - "https://competitor1.com/"

keywords:
  seeds:                             # 8-12 seed keywords
    - "your main keyword"

context:
  brand_voice: |                     # How your brand talks
    ...
  unique_selling_points:             # What makes you different
    - "USP 1"
  products:                          # Your products/services
    - name: "Product"
      description: "..."
  image_style:                       # Guide for AI image generation
    description: "..."
    visual_elements: "..."
    color_palette: "..."
```

## Project Structure

```
seo-blog-engine/
├── run.py                    # CLI entry point
├── orchestrator.py           # Main pipeline (research, generate, publish)
├── config.example.yaml       # Config template
├── requirements.txt
│
├── tools/                    # Research & analysis
│   ├── autocomplete.py       # Google Autocomplete keyword expansion
│   ├── trends.py             # Google Trends data & scoring
│   ├── serp_scraper.py       # Google SERP scraping (results, PAA, related)
│   ├── competitor_analyzer.py# Competitor page analysis (headings, word count, keywords)
│   ├── site_context.py       # Scrape own site for brand context
│   └── blog_analyzer.py      # Analyze existing blog posts for gaps
│
├── generator/                # AI content generation
│   ├── gemini_client.py      # Gemini API calls (text + Imagen images)
│   └── prompts.py            # Prompt templates for blog, edit, rewrite, images
│
├── publisher/                # Publishing pipeline
│   ├── post_publisher.py     # Orchestrates publish/update flow
│   ├── mongodb_client.py     # MongoDB CRUD operations
│   ├── supabase_client.py    # Supabase image upload
│   └── tiptap_converter.py   # Markdown → TipTap JSON (for CMS rendering)
│
├── whatsapp/                 # Human approval flow
│   └── send_and_wait.js      # Send preview via WhatsApp, wait for approve/reject/feedback
│
├── companies_logos/          # Brand logos for image generation
└── output/                   # Drafts & update history (gitignored)
```

## WhatsApp Approval Flow

Before publishing, the engine sends a preview to your WhatsApp. Reply with:

- **"approve"** / **"אישור"** — publish the post
- **"cancel"** / **"ביטול"** — reject (draft saved locally)
- **Any other text** — treated as feedback, Gemini revises the post and re-sends for review

Up to 3 review rounds are supported. If no reply within the timeout (default 30 min), the post is auto-approved.

## Multi-Site Support

Run the same engine for multiple sites by creating separate config files:

```
config.yaml            # Default site
config.pawly.yaml      # Pet food site
config.everst.yaml     # Education platform
config.apps4all.yaml   # Tech company
```

Each config defines its own keywords, competitors, brand voice, MongoDB collection, and publishing targets.

## Tech Stack

- **Gemini 2.5 Flash** — blog post generation, content rewriting, prompt-driven SEO
- **Imagen 4** — AI-generated blog header images (desktop + mobile)
- **Google Trends** — keyword scoring by search interest
- **Google Autocomplete** — long-tail keyword discovery
- **MongoDB** — blog post storage (TipTap JSON format)
- **Supabase** — image hosting (S3-compatible storage)
- **whatsapp-web.js** — human-in-the-loop approval via WhatsApp
