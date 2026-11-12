import { api } from './client'

export type ExamEvent = 'tab_hidden' | 'window_blur' | 'fullscreen_exit' | 'copy' | 'paste'
export type ScorePolicy = 'highest' | 'last'
export type ShowResult = 'never' | 'after_submit' | 'after_close'
export interface ExamDraftInput {
  title: string; description: string | null; duration_min: number; open_at: string; close_at: string
  shuffle_questions: boolean; shuffle_options: boolean; max_attempts: number
  score_policy: ScorePolicy; show_result: ShowResult; require_fullscreen: boolean
  record_events: boolean; violation_types: ExamEvent[]; max_violations: number
  auto_submit_on_violation: boolean; questions: { question_id: number; points: string }[]
}
export interface ExamDraft extends Omit<ExamDraftInput, 'questions'> {
  id: number; class_id: number; status: 'draft' | 'published' | 'closed'; created_at: string
  has_attempts: boolean; total_points: string
  questions: { question_id: number; points: string; order_no: number; content: string; type: string }[]
}
export const examDraftApi = {
  list: async (classId: number, page: number) => (await api.get<{items: ExamDraft[]; total: number}>(`/classes/${classId}/exams`, { params: { page, page_size: 20 } })).data,
  create: async (classId: number, data: ExamDraftInput) => (await api.post<ExamDraft>(`/classes/${classId}/exams`, data)).data,
  update: async (id: number, data: ExamDraftInput) => (await api.put<ExamDraft>(`/exams/${id}`, data)).data,
  remove: async (id: number) => api.delete(`/exams/${id}`),
}
