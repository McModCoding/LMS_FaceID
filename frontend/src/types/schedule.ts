export interface Schedule {
  id: number
  class_id: number
  weekday: number // 0=Thứ Hai, 6=Chủ Nhật
  start_time: string // HH:mm:ss
  end_time: string // HH:mm:ss
  room: string
  start_date: string // YYYY-MM-DD
  end_date: string // YYYY-MM-DD
  created_at?: string
}

export interface ScheduleCreateDTO {
  weekday: number
  start_time: string
  end_time: string
  room: string
  start_date: string
  end_date: string
}

export interface ScheduleUpdateDTO {
  weekday?: number
  start_time?: string
  end_time?: string
  room?: string
  start_date?: string
  end_date?: string
}
