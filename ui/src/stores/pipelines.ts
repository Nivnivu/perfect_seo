import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface LogLine {
  text: string
  type: 'info' | 'success' | 'warning' | 'error' | 'dim'
}

export interface PipelineRun {
  id: number
  site_id: string
  site_name: string | null
  mode: string
  started_at: string
  finished_at: string | null
  exit_code: number | null
  log_preview: string | null
}

export const usePipelinesStore = defineStore('pipelines', () => {
  const logs = ref<LogLine[]>([])
  const isRunning = ref(false)
  const exitCode = ref<number | null>(null)
  const runId = ref<number | null>(null)
  const history = ref<PipelineRun[]>([])
  const pendingReviewId = ref<number | null>(null)

  function classifyLine(text: string): LogLine['type'] {
    if (text.startsWith('[ERROR]') || text.toLowerCase().includes('error:')) return 'error'
    if (text.startsWith('[WARNING]') || text.startsWith('⚠')) return 'warning'
    if (text.startsWith('✅') || text.startsWith('[SUCCESS]') || text.startsWith('✓')) return 'success'
    if (text.startsWith('─') || text.startsWith('▶') || text.startsWith('  Config:')) return 'dim'
    return 'info'
  }

  async function run(siteId: string, mode: string, keywords?: string[], manualPublish = false) {
    if (isRunning.value) return
    isRunning.value = true
    exitCode.value = null
    runId.value = null
    pendingReviewId.value = null
    logs.value = []

    try {
      const response = await fetch('/api/pipelines/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ site_id: siteId, mode, keywords: keywords?.length ? keywords : null, manual_publish: manualPublish }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: response.statusText }))
        logs.value.push({ text: `[ERROR] ${err.detail ?? response.statusText}`, type: 'error' })
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n')
        buffer = parts.pop() ?? ''

        for (const line of parts) {
          if (!line.startsWith('data: ')) continue
          const text = line.slice(6).trim()
          if (!text) continue
          if (text.startsWith('__RUN_ID__')) {
            runId.value = parseInt(text.slice(10)) || null
          } else if (text.startsWith('__EXIT__')) {
            exitCode.value = parseInt(text.slice(8)) || 0
          } else if (text.startsWith('__REVIEW_READY__')) {
            pendingReviewId.value = parseInt(text.slice(16)) || null
          } else {
            logs.value.push({ text, type: classifyLine(text) })
          }
        }
      }
    } catch (e: any) {
      logs.value.push({ text: `[ERROR] ${e.message}`, type: 'error' })
    } finally {
      isRunning.value = false
    }
  }

  async function abort() {
    if (!runId.value) return
    try {
      await fetch(`/api/pipelines/run/${runId.value}`, { method: 'DELETE' })
      logs.value.push({ text: '⚠ Pipeline aborted by user.', type: 'warning' })
    } catch (e: any) {
      logs.value.push({ text: `[ERROR] Abort failed: ${e.message}`, type: 'error' })
    }
  }

  function downloadLog() {
    if (!logs.value.length) return
    const content = logs.value.map((l) => l.text).join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `pipeline-log-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function fetchHistory(siteId?: string) {
    try {
      const url = siteId ? `/api/pipelines/history?site_id=${siteId}&limit=20` : '/api/pipelines/history?limit=20'
      const res = await fetch(url)
      if (res.ok) history.value = await res.json()
    } catch {
      // silently ignore
    }
  }

  function clear() {
    logs.value = []
    exitCode.value = null
    runId.value = null
    pendingReviewId.value = null
  }

  return { logs, isRunning, exitCode, runId, pendingReviewId, history, run, abort, downloadLog, fetchHistory, clear }
})
