export interface TimetableSession {
  session_id: number
  class_id: number
  class_code: string
  subject_name: string
  subject_code: string
  date: string // YYYY-MM-DD
  start_time: string // HH:mm:ss
  end_time: string // HH:mm:ss
  room: string
  status: string
  lecturer_id?: number | null
  lecturer_name?: string | null
}

export interface TimetableResponse {
  items: TimetableSession[]
  total: number
}
