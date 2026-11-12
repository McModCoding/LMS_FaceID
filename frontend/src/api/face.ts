import { api } from './client'

export type FaceProfile = { consented: boolean; cleanup_pending: boolean; text_version?: string | null; consented_at?: string | null; image_count: number; status?: string | null }
export type FaceEnrollmentResult = { accepted: number; rejected: number; status: string; items: { filename?: string | null; accepted: boolean; reason?: string | null }[] }
export type FaceResult = { box: { x: number; y: number; w: number; h: number; det_score: number }; student_id?: number | null; status: 'matched' | 'unknown' | 'ambiguous' | 'low_quality'; score?: number | null; margin?: number | null }
export type RecognitionResponse = { engine: string; ready: boolean; faces: FaceResult[]; attendance_changes: { student_id: number; status: string; result: string; hit_count: number }[] }
export type RecognitionFeedItem = { id: number; student_id?: number | null; status: string; score?: number | null; margin?: number | null; engine_name: string; frame_at: string }
export type RecognitionFeed = { needs_confirmation: RecognitionFeedItem[]; logs: RecognitionFeedItem[] }

export const faceApi = {
  getProfile: () => api.get<FaceProfile>('/students/me/face').then(r => r.data),
  consent: (text_version: string) => api.post<FaceProfile>('/students/me/face/consent', { text_version }).then(r => r.data),
  revoke: () => api.delete<FaceProfile>('/students/me/face/consent').then(r => r.data),
  enroll: (images: File[]) => { const body = new FormData(); images.forEach(image => body.append('images', image)); return api.post<FaceEnrollmentResult>('/students/me/face/enroll', body, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data) },
  status: () => api.get<{ engine: string; version: string; is_ready: boolean }>('/face/status').then(r => r.data),
  reindex: () => api.post<{ processed: number; activated: number }>('/admin/face/reindex').then(r => r.data),
  recognize: (sessionId: number, frame: Blob, frameId = crypto.randomUUID()) => { const body = new FormData(); body.append('frame', frame, 'frame.jpg'); body.append('frame_id', frameId); return api.post<RecognitionResponse>(`/sessions/${sessionId}/recognize`, body, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data) },
  feed: (sessionId: number) => api.get<RecognitionFeed>(`/sessions/${sessionId}/recognition-feed`).then(r => r.data),
}
