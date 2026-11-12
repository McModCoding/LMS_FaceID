export type StudentStatus = 'studying' | 'suspended' | 'graduated'

export interface Student {
  id: number
  user_id: number
  student_code: string
  full_name: string
  admin_class?: string | null
  dob?: string | null
  gender?: string | null
  phone?: string | null
  email?: string | null
  department_id?: number | null
  department_name?: string | null
  status: StudentStatus
  is_deleted?: boolean
  user_is_active?: boolean
  created_at?: string
}

export interface CreateStudentDTO {
  student_code: string
  full_name: string
  admin_class?: string
  email: string
  dob?: string
  gender?: string
  phone?: string
  status?: StudentStatus
  department_id?: number | null
}

export interface UpdateStudentDTO {
  full_name?: string
  admin_class?: string
  email?: string
  dob?: string
  gender?: string
  phone?: string
  status?: StudentStatus
  department_id?: number | null
  is_active?: boolean
}

export interface StudentCreateResponse {
  student: Student
  temp_password?: string
}

// Matches backend response fields exactly
export interface ImportPreviewRow {
  row: number
  student_code?: string
  full_name?: string
  admin_class?: string
  email?: string
  dob?: string
  gender?: string
  phone?: string
  department_code?: string
  department_name?: string
  reason?: string
}

export interface StudentImportPreview {
  valid_rows: ImportPreviewRow[]
  warning_rows: ImportPreviewRow[]
  error_rows: ImportPreviewRow[]
  total_rows: number
  valid_count: number
  warning_count: number
  error_count: number
}
