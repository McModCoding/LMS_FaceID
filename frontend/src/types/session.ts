export type SessionStatus = 'scheduled' | 'open' | 'closed' | 'cancelled'

export interface Session {
  id: number
  class_id: number
  schedule_id?: number | null
  session_no: number
  date: string // YYYY-MM-DD
  start_time: string // HH:mm:ss
  end_time: string // HH:mm:ss
  room: string
  status: SessionStatus
  opened_at?: string | null
  closed_at?: string | null
  created_at: string
}

export interface SessionListResponse {
  items: Session[]
  total: number
}

export interface SessionUpdateDTO {
  date?: string
  start_time?: string
  end_time?: string
  room?: string
}

export interface SessionMakeupCreateDTO {
  date: string
  start_time: string
  end_time: string
  room: string
}
