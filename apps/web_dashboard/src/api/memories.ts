import { apiRequest } from './client'
import type { Memory, MemoryCorrection, MemoryCreate, MemoryReview, MemoryStatus } from './types'

const base = (pid: string) => `/patients/${encodeURIComponent(pid)}/memories`

export const listMemories = (pid: string, status?: MemoryStatus, signal?: AbortSignal) =>
  apiRequest<Memory[]>(base(pid), { query: { status }, signal })
export const createMemory = (pid: string, body: MemoryCreate) =>
  apiRequest<Memory>(base(pid), { method: 'POST', body })
export const correctMemory = (pid: string, mid: string, body: MemoryCorrection) =>
  apiRequest<Memory>(`${base(pid)}/${encodeURIComponent(mid)}`, { method: 'PATCH', body })
export const approveMemory = (pid: string, mid: string, body: MemoryReview) =>
  apiRequest<Memory>(`${base(pid)}/${encodeURIComponent(mid)}/approve`, { method: 'POST', body })
export const rejectMemory = (pid: string, mid: string, body: MemoryReview) =>
  apiRequest<Memory>(`${base(pid)}/${encodeURIComponent(mid)}/reject`, { method: 'POST', body })
export const deleteMemory = (pid: string, mid: string) =>
  apiRequest<void>(`${base(pid)}/${encodeURIComponent(mid)}`, {
    method: 'DELETE',
    responseType: 'none',
  })
