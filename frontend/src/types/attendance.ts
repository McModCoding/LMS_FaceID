export type AttendanceStatus = 'present' | 'late' | 'absent' | 'excused'
export type AttendanceSource = 'manual' | 'system' | 'leave' | 'face'

export interface AttendanceRecord {
  id: number
  session_id: number
  student_id: number
  student_code?: string | null
  full_name?: string | null
  status: AttendanceStatus
  source: AttendanceSource
  display_status: AttendanceStatus | 'pending'
  note?: string | null
}

export interface AttendanceSummary {
  total: number
  present: number
  late: number
  absent: number
  excused: number
  pending: number
}

export interface SessionAttendanceResponse {
  session_id: number
  session_status: string
  can_edit: boolean
  summary: AttendanceSummary
  items: AttendanceRecord[]
  total: number
  page: number
  page_size: number
}
