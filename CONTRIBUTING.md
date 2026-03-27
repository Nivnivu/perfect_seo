# Contributing to SEO Blog Engine

Thanks for your interest in contributing! This document covers how to set up a development environment and guidelines for submitting changes.

---

## Dev Environment

### Prerequisites
- Python 3.10+
- Node.js 18+
- Git Bash (Windows) or any Unix shell

### Setup

```bash
git clone https://github.com/your-username/seo-blog-engine.git
cd seo-blog-engine

# Install Python dependencies
pip install -r requirements.txt
pip install -r api/requirements.txt

# Install UI dependencies
cd ui && npm install && cd ..

# Start dev servers (auto-reloads on file changes)
./start.sh
```

The API uses `--reload` mode by default, so any Python change applies immediately. The Vue UI uses Vite HMR.

---

## Project Layout

| Path | What it is |
|---|---|
| `api/` | FastAPI backend — routes, config manager, models |
| `publishers/` | Platform publisher abstraction (MongoDB, WP, Shopify, Wix, WC) |
| `tools/` | SEO research tools (GSC, SERP scraper, analyzer) |
| `generator/` | AI prompt building and API calls |
| `publisher/` | MongoDB publishing pipeline (legacy, still used by orchestrator) |
| `ui/src/views/` | Vue page components |
| `ui/src/components/` | Reusable UI components (sidebar, wizard, charts) |
| `ui/src/stores/` | Pinia state stores |

---

## Adding a New Platform

1. Create `publishers/yourplatform.py` implementing `BasePlatformPublisher`
2. Add the case to `publishers/factory.py`
3. Add platform card to `ui/src/components/wizard/StepPlatform.vue`
4. Add credential fields to `ui/src/components/wizard/StepCredentials.vue`
5. Add test-connection logic to `api/routes/sites.py`
6. Add a `config.example.yourplatform.yaml`

---

## Adding a New AI Provider

1. Add provider config to `publishers/` if it needs a new client (or use OpenAI-compatible endpoint)
2. Add provider card + model list to `ui/src/components/wizard/StepSiteInfo.vue`
3. Add the provider key to the union type in `ui/src/stores/wizard.ts`
4. Add a case in `buildConfig()` in `wizard.ts` if needed

---

## Code Style

**Python:** Follow PEP 8. Use `ruff check` before committing.

```bash
pip install ruff
ruff check api/ publishers/ tools/ generator/ publisher/
```

**TypeScript/Vue:** Follow the existing patterns — `<script setup lang="ts">`, composables in `stores/`, shadcn-style components in `components/ui/`.

---

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Update `UI_PLAN.md` if you're completing a planned feature
- Add a `config.example.*.yaml` for any new platform
- Test with at least one real site config before submitting
- PRs that touch `orchestrator.py` need extra care — the pipeline has GSC protection logic

---

## Issues

Report bugs and feature requests at [GitHub Issues](https://github.com/your-username/seo-blog-engine/issues).
