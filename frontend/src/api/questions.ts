import { api } from './client'

export type QuestionType = 'single' | 'multiple' | 'true_false' | 'essay'
export type Difficulty = 'easy' | 'medium' | 'hard'
export interface QuestionInput {
  type: QuestionType
  content: string
  difficulty: Difficulty
  explanation: string | null
  options: { content: string; is_correct: boolean }[]
}
export interface Question extends QuestionInput { id: number; subject_id: number; created_by: number; can_edit: boolean }
export interface QuestionList { items: Question[]; total: number; page: number; page_size: number }
export interface ImportPreview { valid: { row: number; item: QuestionInput }[]; errors: { row: number; message: string }[] }

export const questionsApi = {
  list: async (subject: number, params: Record<string, string | number>) => (await api.get<QuestionList>(`/subjects/${subject}/questions`, { params })).data,
  create: async (subject: number, data: QuestionInput) => (await api.post(`/subjects/${subject}/questions`, data)).data,
  update: async (id: number, data: QuestionInput) => (await api.put(`/questions/${id}`, data)).data,
  remove: async (id: number) => api.delete(`/questions/${id}`),
  template: async (subject: number) => (await api.get(`/subjects/${subject}/questions/import/template`, { responseType: 'blob' })).data as Blob,
  preview: async (subject: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return (await api.post<ImportPreview>(`/subjects/${subject}/questions/import/preview`, form, { headers: { 'Content-Type': 'multipart/form-data' } })).data
  },
  confirm: async (subject: number, items: QuestionInput[]) => (await api.post<{ created: number }>(`/subjects/${subject}/questions/import/confirm`, { items })).data,
}
