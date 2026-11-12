export interface ConflictItem {
  conflict_type: 'room' | 'lecturer' | 'student' | string
  class_id: number
  class_code: string
  session_id: number
  date: string
  start_time: string
  end_time: string
  room: string
  conflicting_entity: string
  message: string
}

export interface ConflictErrorResponse {
  code: string
  message: string
  conflicts?: ConflictItem[]
}
