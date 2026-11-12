import { api } from './client'

export type StudentExamStatus = 'upcoming' | 'available' | 'in_progress' | 'retry_available' | 'completed' | 'closed'
export interface StudentExam {
  id: number
  title: string
  description: string | null
  duration_min: number
  open_at: string
  close_at: string
  max_attempts: number
  used_attempts: number
  question_count: number
  record_events: boolean
  violation_types: string[]
  max_violations: number
  auto_submit_on_violation: boolean
  require_fullscreen: boolean
  active_attempt_id: number | null
  status: StudentExamStatus
}
export interface StudentExamPage {
  items: StudentExam[]
  total: number
  page: number
  page_size: number
}
export interface StudentExamOption { id: number; content: string }
export interface StudentExamQuestion {
  question_id: number
  type: 'single' | 'multiple' | 'true_false' | 'essay'
  content: string
  points: string
  options: StudentExamOption[]
  selected_option_ids: number[] | null
  essay_text: string | null
}
export interface StudentExamAttempt {
  id: number
  exam_id: number
  class_id: number
  exam_title: string
  record_events: boolean
  violation_types: string[]
  max_violations: number
  auto_submit_on_violation: boolean
  violation_count: number
  is_auto_submitted: boolean
  require_fullscreen: boolean
  attempt_no: number
  status: 'in_progress' | 'submitted' | 'auto_submitted' | 'graded'
  started_at: string
  deadline_at: string
  server_now: string
  questions: StudentExamQuestion[]
}

export const studentExamsApi = {
  list: async (classId: number, page = 1) => (await api.get<StudentExamPage>(`/classes/${classId}/student-exams`, { params: { page, page_size: 20 } })).data,
  begin: async (examId: number) => (await api.post<StudentExamAttempt>(`/exams/${examId}/attempts`)).data,
  getAttempt: async (attemptId: number) => (await api.get<StudentExamAttempt>(`/attempts/${attemptId}`)).data,
  saveAnswer: async (attemptId: number, questionId: number, answer: { selected_option_ids?: number[] | null; essay_text?: string | null }) =>
    api.put(`/attempts/${attemptId}/answers/${questionId}`, answer),
  submit: async (attemptId: number) => (await api.post<StudentExamAttempt>(`/attempts/${attemptId}/submit`)).data,
}
