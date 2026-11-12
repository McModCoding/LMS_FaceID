export type ClassStatus = 'draft' | 'active' | 'closed'
export type ClassStudentStatus = 'enrolled' | 'dropped'

export interface Class {
  id: number
  code: string
  subject_id: number
  subject_name?: string | null
  subject_code?: string | null
  semester_id: number
  semester_name?: string | null
  lecturer_id?: number | null
  lecturer_name?: string | null
  lecturer_code?: string | null
  max_students: number
  enrolled_count: number
  status: ClassStatus
  late_after_min: number
  absent_after_min: number
  weight_present: number
  weight_late: number
  weight_excused: number
  attendance_warning_absences: number
  created_at: string
}

export interface ClassListResponse {
  items: Class[]
  total: number
  page: number
  page_size: number
}

export interface ClassCreateDTO {
  code: string
  subject_id: number
  semester_id: number
  lecturer_id?: number | null
  max_students?: number
  late_after_min?: number
  absent_after_min?: number
  weight_present?: number
  weight_late?: number
  weight_excused?: number
  attendance_warning_absences?: number
}

export interface ClassUpdateDTO {
  lecturer_id?: number | null
  max_students?: number
  late_after_min?: number
  absent_after_min?: number
  weight_present?: number
  weight_late?: number
  weight_excused?: number
  attendance_warning_absences?: number
}

export interface ClassStudent {
  id: number
  student_id: number
  student_code: string
  full_name: string
  status: ClassStudentStatus
  enrolled_at: string
}

export interface ClassStudentListResponse {
  items: ClassStudent[]
  total: number
  page: number
  page_size: number
}

export interface EnrollmentPreviewRow {
  row: number
  student_code: string
  full_name?: string | null
  status: 'ok' | 'warning' | 'error' | string
  reason?: string | null
  [key: string]: any
}

export interface EnrollmentImportPreview {
  valid_rows: EnrollmentPreviewRow[]
  warning_rows: EnrollmentPreviewRow[]
  error_rows: EnrollmentPreviewRow[]
  total_rows: number
  valid_count: number
  warning_count: number
  error_count: number
}
