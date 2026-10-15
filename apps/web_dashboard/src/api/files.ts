import { apiRequest } from './client'
import type { StoredFile } from './types'

export function uploadMedia(patientId: string, file: File): Promise<StoredFile> {
  const form = new FormData()
  form.append('file', file)
  return apiRequest<StoredFile>(`/patients/${encodeURIComponent(patientId)}/media`, {
    method: 'POST',
    form,
    timeoutMs: 60000,
  })
}

/** Files are protected: they are fetched with the sign-in token, never by plain URL. */
export function downloadFile(fileId: string, signal?: AbortSignal): Promise<Blob> {
  return apiRequest<Blob>(`/files/${encodeURIComponent(fileId)}/content`, {
    responseType: 'blob',
    signal,
    timeoutMs: 60000,
  })
}

export const ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp']
