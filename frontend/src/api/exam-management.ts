import { api } from './client'

export interface ExamAttemptSummary {
  id: number; student_id: number; student_code: string; student_name: string
  attempt_no: number; status: string; score: string | null; score10: string | null
  submitted_at: string | null; violation_count: number; is_auto_submitted: boolean
}
export interface ExamReview extends ExamAttemptSummary {
  exam_id: number; class_id: number; exam_title: string; total_points: string
  questions: { question_id: number; content: string; type: string; points: string
    explanation: string | null; options: { id: number; content: string; is_correct: boolean }[]
    selected_option_ids: number[] | null; essay_text: string | null; score: string | null; feedback: string | null }[]
}
export interface ExamResults {
  exam_id: number; title: string; available: boolean; reason: string; score_policy: string
  score10: string | null; selected_attempt_id: number | null
  attempts: { id: number; attempt_no: number; status: string; score10: string | null; is_auto_submitted: boolean }[]
}
export interface ExamStatistics {
  in_progress: number; submitted: number; pending_grading: number; graded_students: number
  average: string | null; highest: string | null; lowest: string | null; score_policy: string
  histogram: { label: string; count: number }[]
  questions: { question_id: number; content: string; type: string; total: number; correct: number | null; correct_rate: string | null }[]
  not_started: { student_id: number; student_code: string; student_name: string }[]
}
export const attemptStatus: Record<string, string> = {
  in_progress: 'Đang làm', submitted: 'Chờ chấm tự luận', auto_submitted: 'Tự nộp · chờ chấm tự luận', graded: 'Đã chấm',
}
export const eventLabels: Record<string, string> = {
  tab_hidden: 'Ẩn tab', window_blur: 'Mất tiêu điểm', fullscreen_exit: 'Thoát toàn màn hình',
  copy: 'Sao chép', paste: 'Dán', reconnect: 'Kết nối lại',
}
export const scoreText = (value: string | null) => value === null ? 'Chưa có' : Number(value).toFixed(2)
export const examManagementApi = {
  publish: (id: number) => api.post(`/exams/${id}/publish`),
  close: (id: number) => api.post(`/exams/${id}/close`),
  closeTime: (id: number, close_at: string) => api.patch(`/exams/${id}/close-time`, { close_at }),
  attempts: async (id: number, page: number, state = '') => (await api.get<{ items: ExamAttemptSummary[]; total: number }>(`/exams/${id}/attempts`, { params: { page, page_size: 20, state: state || undefined } })).data,
  review: async (id: number) => (await api.get<ExamReview>(`/attempts/${id}/review`)).data,
  result: async (id: number) => (await api.get<ExamReview>(`/attempts/${id}/result`)).data,
  results: async (id: number) => (await api.get<ExamResults>(`/exams/${id}/results`)).data,
  grade: async (id: number, qid: number, score: string, feedback: string) => (await api.post<ExamReview>(`/attempts/${id}/questions/${qid}/grade`, { score, feedback })).data,
  stats: async (id: number) => (await api.get<ExamStatistics>(`/exams/${id}/stats`)).data,
  export: async (id: number) => (await api.get<Blob>(`/exams/${id}/export`, { responseType: 'blob' })).data,
  events: async (id: number, page: number) => (await api.get<{ items: { id: number; type: string; occurred_at: string; counted: boolean }[]; total: number }>(`/attempts/${id}/events`, { params: { page, page_size: 20 } })).data,
  event: async (id: number, event_id: string, type: string) => (await api.post<{ recorded: boolean; violation_count: number; status: string; is_auto_submitted: boolean }>(`/attempts/${id}/events`, { event_id, type })).data,
}
