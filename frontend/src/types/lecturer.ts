export type LecturerType = 'full_time' | 'visiting'

export interface Lecturer {
  id: number
  user_id: number
  code: string
  full_name: string
  phone?: string | null
  email?: string | null
  degree?: string | null
  department?: string | null
  department_id?: number | null
  department_name?: string | null
  type: LecturerType
  user_is_active?: boolean
  is_active?: boolean
  created_at?: string
  updated_at?: string
}

export interface CreateLecturerDTO {
  code: string
  full_name: string
  email: string
  phone?: string
  degree?: string
  department?: string
  department_id?: number | null
  type: LecturerType
}

export interface UpdateLecturerDTO {
  full_name?: string
  email?: string
  phone?: string
  degree?: string
  department?: string
  department_id?: number | null
  type?: LecturerType
}

export interface LecturerCreateResponse {
  lecturer: Lecturer
  temp_password?: string
}
