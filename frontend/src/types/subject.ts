export interface Subject {
  id: number
  code: string
  name: string
  credits: number
  department_id?: number | null
  department_name?: string | null
  created_at?: string
  updated_at?: string
}

export interface CreateSubjectDTO {
  code: string
  name: string
  credits: number
  department_id?: number
}

export interface UpdateSubjectDTO {
  code?: string
  name?: string
  credits?: number
  department_id?: number | null
}
