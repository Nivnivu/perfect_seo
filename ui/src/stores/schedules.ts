import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export interface Schedule {
  id: number
  site_id: string
  mode: string
  cron_expr: string
  label: string
  keywords: string[]
  manual_publish: number
  enabled: number
  created_at: string
  last_run_at: string | null
  next_run_at: string | null
}

export interface ScheduleRun {
  id: number
  schedule_id: number
  site_id: string
  mode: string
  started_at: string
  finished_at: string | null
  exit_code: number | null
  log_path: string | null
}

export const useSchedulesStore = defineStore('schedules', () => {
  const schedules = ref<Schedule[]>([])

  async function fetchSchedules() {
    try {
      const res = await axios.get('/api/schedules')
      schedules.value = res.data
    } catch { /* ignore */ }
  }

  async function createSchedule(payload: {
    site_id: string; mode: string; cron_expr: string
    label?: string; keywords?: string[]; manual_publish?: boolean; enabled?: boolean
  }): Promise<Schedule> {
    const res = await axios.post('/api/schedules', payload)
    schedules.value.unshift(res.data)
    return res.data
  }

  async function updateSchedule(id: number, payload: Partial<{
    mode: string; cron_expr: string; label: string
    keywords: string[]; manual_publish: boolean; enabled: boolean
  }>): Promise<Schedule> {
    const res = await axios.put(`/api/schedules/${id}`, payload)
    const idx = schedules.value.findIndex(s => s.id === id)
    if (idx >= 0) schedules.value[idx] = res.data
    return res.data
  }

  async function deleteSchedule(id: number) {
    await axios.delete(`/api/schedules/${id}`)
    schedules.value = schedules.value.filter(s => s.id !== id)
  }

  async function toggleSchedule(id: number): Promise<Schedule> {
    const res = await axios.post(`/api/schedules/${id}/toggle`)
    const idx = schedules.value.findIndex(s => s.id === id)
    if (idx >= 0) schedules.value[idx] = res.data
    return res.data
  }

  async function fetchRuns(scheduleId: number): Promise<ScheduleRun[]> {
    const res = await axios.get(`/api/schedules/${scheduleId}/runs`)
    return res.data
  }

  async function fetchRunLog(scheduleId: number, runId: number): Promise<string> {
    const res = await axios.get(`/api/schedules/${scheduleId}/runs/${runId}/log`)
    return res.data.content
  }

  return {
    schedules,
    fetchSchedules,
    createSchedule,
    updateSchedule,
    deleteSchedule,
    toggleSchedule,
    fetchRuns,
    fetchRunLog,
  }
})
