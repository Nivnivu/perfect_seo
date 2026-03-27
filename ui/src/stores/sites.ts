import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export interface SiteSummary {
  id: string
  file: string
  name: string
  domain: string
  language: string
  platform: string
  has_gsc: boolean
}

export const useSitesStore = defineStore('sites', () => {
  const sites = ref<SiteSummary[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchSites() {
    loading.value = true
    error.value = null
    try {
      const { data } = await axios.get<SiteSummary[]>('/api/sites')
      sites.value = data
    } catch (e: any) {
      error.value = e.message ?? 'Failed to load sites'
    } finally {
      loading.value = false
    }
  }

  async function deleteSite(siteId: string) {
    await axios.delete(`/api/sites/${siteId}`)
    await fetchSites()
  }

  return { sites, loading, error, fetchSites, deleteSite }
})
