import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export interface Review {
  id: number
  site_id: string
  mode: string
  status: 'pending' | 'published' | 'rejected'
  title: string
  subtitle: string
  body_html: string
  body_markdown: string
  image_base64: string | null
  topic: string
  post_id: string | null
  original_title: string | null
  original_body: string | null
  subtitle_only: number
  created_at: string
  published_at: string | null
}

export const useReviewsStore = defineStore('reviews', () => {
  const reviews = ref<Review[]>([])
  const pendingCount = computed(() => reviews.value.filter(r => r.status === 'pending').length)

  async function fetchReviews(status = 'pending') {
    try {
      const res = await axios.get('/api/reviews', { params: { status } })
      reviews.value = res.data
    } catch {
      // silently ignore
    }
  }

  async function fetchPendingCount() {
    try {
      const res = await axios.get('/api/reviews/count')
      return res.data.count as number
    } catch {
      return 0
    }
  }

  async function fetchReview(id: number): Promise<Review | null> {
    try {
      const res = await axios.get(`/api/reviews/${id}`)
      return res.data
    } catch {
      return null
    }
  }

  async function publishReview(
    id: number,
    payload: { title: string; subtitle: string; body_html: string },
  ): Promise<{ post_id: string }> {
    const res = await axios.post(`/api/reviews/${id}/publish`, payload)
    await fetchReviews()
    return res.data
  }

  async function rejectReview(id: number): Promise<void> {
    await axios.post(`/api/reviews/${id}/reject`)
    reviews.value = reviews.value.filter(r => r.id !== id)
  }

  async function refineReview(
    id: number,
    instruction: string,
    body_html: string,
  ): Promise<string> {
    const res = await axios.post(`/api/reviews/${id}/refine`, { instruction, body_html })
    return res.data.body_html
  }

  return {
    reviews,
    pendingCount,
    fetchReviews,
    fetchPendingCount,
    fetchReview,
    publishReview,
    rejectReview,
    refineReview,
  }
})
