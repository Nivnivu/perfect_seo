import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import axios from 'axios'
import { useSitesStore } from './sites'

const COUNTRY_TO_DOMAIN: Record<string, string> = {
  us: 'google.com', gb: 'google.co.uk', il: 'google.co.il',
  de: 'google.de', fr: 'google.fr', es: 'google.es',
  it: 'google.it', au: 'google.com.au', ca: 'google.ca',
  br: 'google.com.br', in: 'google.co.in', jp: 'google.co.jp',
}

const DEFAULT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

function defaultForm() {
  return {
    // Step 0 – Platform
    platform: 'wordpress' as 'mongodb' | 'wordpress' | 'woocommerce' | 'shopify' | 'wix',

    // Step 1 – Site Info & AI
    site_id: '',
    site_name: '',
    domain: '',
    blog_url: '',
    language: 'en',
    country: 'us',
    google_domain: 'google.com',
    ai_provider: 'gemini' as 'gemini' | 'openai' | 'anthropic' | 'mistral' | 'deepseek',
    ai_api_key: '',
    ai_model: 'gemini-2.5-flash',
    ai_image_model: 'imagen-4.0-fast-generate-001',

    // Step 2 – Credentials: MongoDB
    mongodb_uri: '',
    mongodb_database: 'multiBlogDB',
    mongodb_collection: '',
    // Supabase (shared by MongoDB + WordPress)
    supabase_url: '',
    supabase_key: '',
    supabase_bucket: 'blog-poster',
    // WordPress
    wp_site_url: '',
    wp_username: '',
    wp_app_password: '',
    // WooCommerce
    wc_site_url: '',
    wc_consumer_key: '',
    wc_consumer_secret: '',
    // Shopify
    shopify_store_domain: '',
    shopify_admin_api_token: '',
    // Wix
    wix_api_key: '',
    wix_site_id: '',

    // Step 3 – Search Console (optional)
    gsc_enabled: false,
    gsc_credentials_file: '',
    gsc_site_url: '',
    gsc_min_clicks: 10,
    gsc_min_impressions: 100,
    gsc_max_position: 20.0,

    // Step 4 – Content (all optional)
    seed_keywords: '',
    competitors: '',
    brand_voice: '',
    image_description: '',
    image_visual_elements: '',
    image_color_palette: '',
    unique_selling_points: '',
  }
}

export const useWizardStore = defineStore('wizard', () => {
  const isOpen = ref(false)
  const currentStep = ref(0)
  const saving = ref(false)
  const saveError = ref<string | null>(null)

  const form = reactive(defaultForm())

  // ── Derived helpers ────────────────────────────────────────────────────────

  function deriveGoogleDomain(country: string): string {
    return COUNTRY_TO_DOMAIN[country.toLowerCase()] ?? 'google.com'
  }

  /** Called by StepSiteInfo when country changes */
  function syncGoogleDomain() {
    form.google_domain = deriveGoogleDomain(form.country)
  }

  // ── Validation ─────────────────────────────────────────────────────────────

  function validateStep(step: number): string | null {
    switch (step) {
      case 0:
        return null

      case 1: {
        if (!form.site_id.trim()) return 'Site ID is required'
        if (!/^[a-z0-9_-]+$/.test(form.site_id)) return 'Site ID: only lowercase letters, numbers, hyphens, underscores'
        if (!form.site_name.trim()) return 'Site name is required'
        if (!form.domain.trim()) return 'Domain is required'
        if (!form.ai_api_key.trim()) return 'AI API key is required'
        return null
      }

      case 2: {
        if (form.platform === 'mongodb') {
          if (!form.mongodb_uri.trim()) return 'MongoDB URI is required'
          if (!form.mongodb_collection.trim()) return 'MongoDB collection name is required'
        } else if (form.platform === 'wordpress') {
          if (!form.wp_site_url.trim()) return 'WordPress site URL is required'
          if (!form.wp_username.trim()) return 'WordPress username is required'
          if (!form.wp_app_password.trim()) return 'WordPress application password is required'
        } else if (form.platform === 'woocommerce') {
          if (!form.wc_site_url.trim()) return 'WooCommerce site URL is required'
          if (!form.wc_consumer_key.trim()) return 'Consumer key is required'
          if (!form.wc_consumer_secret.trim()) return 'Consumer secret is required'
        } else if (form.platform === 'shopify') {
          if (!form.shopify_store_domain.trim()) return 'Store domain is required'
          if (!form.shopify_admin_api_token.trim()) return 'Admin API token is required'
        } else if (form.platform === 'wix') {
          if (!form.wix_api_key.trim()) return 'Wix API key is required'
          if (!form.wix_site_id.trim()) return 'Wix site ID is required'
        }
        return null
      }

      case 3:
      case 4:
      case 5:
        return null

      default:
        return null
    }
  }

  // ── Config builder ──────────────────────────────────────────────────────────

  function buildConfig() {
    const lines = (raw: string) =>
      raw.split('\n').map((s) => s.trim()).filter(Boolean)

    const config: Record<string, any> = {
      platform: form.platform,
    }

    // AI provider block (key name matches provider id)
    const aiBlock: Record<string, any> = { api_key: form.ai_api_key, model: form.ai_model }
    if (form.ai_image_model) aiBlock.image_model = form.ai_image_model
    config[form.ai_provider] = aiBlock

    config.site = {
      name: form.site_name,
      domain: form.domain,
      blog_url: form.blog_url || `https://${form.domain}/blog`,
      language: form.language,
      country: form.country,
      google_domain: form.google_domain,
    }
    config.scraping = { user_agent: DEFAULT_UA, request_delay: 2 }

    if (form.platform === 'mongodb') {
      config.mongodb = { uri: form.mongodb_uri, database: form.mongodb_database, collection: form.mongodb_collection }
      config.supabase = { url: form.supabase_url, key: form.supabase_key, bucket: form.supabase_bucket }
    } else if (form.platform === 'wordpress') {
      config.wordpress = { site_url: form.wp_site_url, username: form.wp_username, app_password: form.wp_app_password }
      config.supabase = { url: form.supabase_url, key: form.supabase_key, bucket: form.supabase_bucket }
    } else if (form.platform === 'woocommerce') {
      config.woocommerce = { site_url: form.wc_site_url, consumer_key: form.wc_consumer_key, consumer_secret: form.wc_consumer_secret }
    } else if (form.platform === 'shopify') {
      config.shopify = { store_domain: form.shopify_store_domain, admin_api_token: form.shopify_admin_api_token }
    } else if (form.platform === 'wix') {
      config.wix = { api_key: form.wix_api_key, site_id: form.wix_site_id }
    }

    if (form.gsc_enabled && form.gsc_credentials_file.trim()) {
      config.search_console = {
        credentials_file: form.gsc_credentials_file,
        token_file: 'gsc_token.json',
        site_url: form.gsc_site_url || `https://${form.domain}/`,
        protection_thresholds: {
          min_clicks: form.gsc_min_clicks,
          min_impressions: form.gsc_min_impressions,
          max_position: form.gsc_max_position,
        },
      }
    }

    config.keywords = { seeds: lines(form.seed_keywords) }
    config.competitors = lines(form.competitors)
    config.context = {
      brand_voice: form.brand_voice,
      image_style: {
        description: form.image_description,
        visual_elements: form.image_visual_elements,
        color_palette: form.image_color_palette,
      },
      unique_selling_points: lines(form.unique_selling_points),
    }

    return { site_id: form.site_id, platform: form.platform, config }
  }

  // ── Actions ─────────────────────────────────────────────────────────────────

  function open() {
    Object.assign(form, defaultForm())
    currentStep.value = 0
    saveError.value = null
    isOpen.value = true
  }

  function close() {
    isOpen.value = false
  }

  async function save() {
    const sitesStore = useSitesStore()
    if (sitesStore.sites.some((s) => s.id === form.site_id)) {
      saveError.value = `Site ID "${form.site_id}" already exists. Use a different ID.`
      return
    }

    saving.value = true
    saveError.value = null
    try {
      const payload = buildConfig()
      await axios.post('/api/sites', payload)
      await sitesStore.fetchSites()
      close()
    } catch (e: any) {
      saveError.value = e.response?.data?.detail ?? e.message ?? 'Failed to save site'
    } finally {
      saving.value = false
    }
  }

  return {
    isOpen, currentStep, saving, saveError,
    form,
    validateStep, buildConfig, syncGoogleDomain,
    open, close, save,
  }
})
