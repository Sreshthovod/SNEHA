import { apiRequest } from './client'
import type {
  Memory,
  MemoryCorrection,
  MemoryCreate,
  MemoryLink,
  MemoryLinkCreate,
  MemoryReview,
  MemoryStatus,
} from './types'

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
export const getMemory = (pid: string, mid: string, signal?: AbortSignal) =>
  apiRequest<Memory>(`${base(pid)}/${encodeURIComponent(mid)}`, { signal })

const links = (pid: string) => `/patients/${encodeURIComponent(pid)}/memory-relationships`
/** Links between memories (e.g. a person in an event). Non-managers see approved ends only. */
export const listMemoryLinks = (pid: string, signal?: AbortSignal) =>
  apiRequest<MemoryLink[]>(links(pid), { signal })
export const createMemoryLink = (pid: string, body: MemoryLinkCreate) =>
  apiRequest<MemoryLink>(links(pid), { method: 'POST', body })
export const deleteMemoryLink = (pid: string, linkId: string) =>
  apiRequest<void>(`${links(pid)}/${encodeURIComponent(linkId)}`, {
    method: 'DELETE',
    responseType: 'none',
  })
