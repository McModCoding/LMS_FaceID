import React from 'react'
import dayjs from 'dayjs'
import 'dayjs/locale/vi'
import {
  ChevronLeft,
  ChevronRight,
  Calendar as CalendarIcon,
  Clock,
  MapPin,
  User,
  CheckCircle2,
  PlayCircle,
  XCircle,
  CalendarDays,
} from 'lucide-react'
import { TimetableSession } from '../../types/timetable'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface WeeklyTimetableProps {
  sessions: TimetableSession[]
  currentDate: Date
  onDateChange: (newDate: Date) => void
  loading?: boolean
  extraHeaderActions?: React.ReactNode
  showLecturer?: boolean
}

const WEEKDAY_NAMES = [
  'Thứ Hai',
  'Thứ Ba',
  'Thứ Tư',
  'Thứ Năm',
  'Thứ Sáu',
  'Thứ Bảy',
  'Chủ Nhật',
]

export const WeeklyTimetable: React.FC<WeeklyTimetableProps> = ({
  sessions,
  currentDate,
  onDateChange,
  loading = false,
  extraHeaderActions,
  showLecturer = true,
}) => {
  // Compute Monday of the current week (day 0=Sun, 1=Mon, ..., 6=Sat in JS Date)
  const currentDayOfWeek = dayjs(currentDate).day() // 0 is Sunday, 1 is Monday
  // Convert so Monday is 0, Sunday is 6
  const mondayOffset = currentDayOfWeek === 0 ? -6 : 1 - currentDayOfWeek
  const monday = dayjs(currentDate).add(mondayOffset, 'day')

  const weekDays = Array.from({ length: 7 }).map((_, i) => {
    const d = monday.add(i, 'day')
    return {
      dayName: WEEKDAY_NAMES[i],
      dateStr: d.format('YYYY-MM-DD'),
      displayDate: d.format('DD/MM/YYYY'),
      isToday: d.isSame(dayjs(), 'day'),
    }
  })

  const handlePrevWeek = () => {
    onDateChange(dayjs(currentDate).subtract(7, 'day').toDate())
  }

  const handleNextWeek = () => {
    onDateChange(dayjs(currentDate).add(7, 'day').toDate())
  }

  const handleToday = () => {
    onDateChange(new Date())
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'scheduled':
        return (
          <Badge variant="outline" className="text-xs bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800 flex items-center gap-1">
            <CalendarDays className="h-3 w-3" /> Lên lịch
          </Badge>
        )
      case 'open':
        return (
          <Badge variant="outline" className="text-xs bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800 flex items-center gap-1">
            <PlayCircle className="h-3 w-3" /> Đang mở
          </Badge>
        )
      case 'closed':
        return (
          <Badge variant="outline" className="text-xs bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700 flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" /> Đã đóng
          </Badge>
        )
      case 'cancelled':
        return (
          <Badge variant="destructive" className="text-xs flex items-center gap-1">
            <XCircle className="h-3 w-3" /> Đã hủy
          </Badge>
        )
      default:
        return <Badge variant="secondary" className="text-xs">{status}</Badge>
    }
  }

  return (
    <div className="space-y-4">

      <div className="flex flex-wrap items-center justify-between gap-3 bg-card p-3 rounded-lg border">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleToday}>
            Hôm nay
          </Button>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="icon" className="h-8 w-8" onClick={handlePrevWeek}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" className="h-8 w-8" onClick={handleNextWeek}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2 ml-1 sm:ml-2">
            <span className="text-sm font-semibold flex items-center gap-1.5 text-foreground">
              <CalendarIcon className="h-4 w-4 text-primary" />
              {weekDays[0].displayDate} — {weekDays[6].displayDate}
            </span>

            <div className="flex items-center gap-1.5 pl-2 sm:border-l sm:border-border/80">
              <label htmlFor="timetable-date-jump" className="text-xs text-muted-foreground whitespace-nowrap hidden md:inline">
                Xem ngày:
              </label>
              <input
                id="timetable-date-jump"
                type="date"
                aria-label="Chọn ngày xem thời khóa biểu"
                title="Chọn ngày cụ thể để chuyển nhanh đến tuần đó"
                className="h-8 rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground cursor-pointer hover:border-primary/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring transition-colors"
                value={dayjs(currentDate).format('YYYY-MM-DD')}
                onChange={(e) => {
                  if (e.target.value) {
                    onDateChange(dayjs(e.target.value).toDate())
                  }
                }}
              />
            </div>
          </div>
        </div>

        {extraHeaderActions && (
          <div className="flex items-center gap-2 flex-wrap">{extraHeaderActions}</div>
        )}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-3 md:min-w-[1120px] md:grid-cols-7">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-12 w-full rounded-md" />
              <Skeleton className="h-28 w-full rounded-md" />
              <Skeleton className="h-28 w-full rounded-md" />
            </div>
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto pb-1"><div className="grid grid-cols-1 gap-3 md:min-w-[1120px] md:grid-cols-7">
          {weekDays.map((day) => {
            const daySessions = sessions
              .filter((s) => s.date === day.dateStr)
              .sort((a, b) => (a.start_time > b.start_time ? 1 : -1))

            return (
              <div
                key={day.dateStr}
                className={cn(
                  'flex flex-col rounded-lg border bg-card overflow-hidden',
                  day.isToday && 'border-primary shadow-sm'
                )}
              >

                <div
                  className={cn(
                    'p-2.5 text-center border-b font-medium text-xs',
                    day.isToday
                      ? 'bg-primary text-primary-foreground font-semibold'
                      : 'bg-muted/50 text-muted-foreground'
                  )}
                >
                  <div className="text-sm">{day.dayName}</div>
                  <div className="text-xs opacity-90">{day.displayDate}</div>
                </div>

                <div className="p-2 flex-1 space-y-2 min-h-[220px] bg-background/50">
                  {daySessions.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground/60 italic py-8">
                      Không có lịch
                    </div>
                  ) : (
                    daySessions.map((session) => {
                      const isCancelled = session.status === 'cancelled'
                      const startTime = session.start_time ? session.start_time.slice(0, 5) : ''
                      const endTime = session.end_time ? session.end_time.slice(0, 5) : ''

                      return (
                        <Card
                          key={session.session_id}
                          className={cn(
                            'p-2.5 text-xs transition-all shadow-none hover:shadow-sm border',
                            isCancelled
                              ? 'opacity-55 bg-muted/60 line-through-text border-dashed'
                              : 'bg-card border-border/80'
                          )}
                        >
                          <CardContent className="p-0 space-y-1.5">
                            <div className={cn('font-semibold text-primary break-words', isCancelled && 'line-through text-muted-foreground')}>
                              {session.class_code}
                            </div>

                            <div
                              className={cn(
                                'font-medium text-foreground break-words',
                                isCancelled && 'line-through text-muted-foreground'
                              )}
                            >
                              {session.subject_name}
                            </div>

                            <div className="space-y-1 text-muted-foreground pt-1 border-t border-border/40 text-[11px]">
                              <div className="flex items-center gap-1">
                                <Clock className="h-3 w-3 shrink-0 text-primary/70" />
                                <span>
                                  {startTime} - {endTime}
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                <MapPin className="h-3 w-3 shrink-0 text-primary/70" />
                                <span className="font-semibold text-foreground/80 break-words">{session.room}</span>
                              </div>
                              {showLecturer && session.lecturer_name && (
                                <div className="flex items-center gap-1">
                                  <User className="h-3 w-3 shrink-0 text-primary/70" />
                                  <span className="break-words">{session.lecturer_name}</span>
                                </div>
                              )}
                            </div>
                            <div className="pt-1">{getStatusBadge(session.status)}</div>
                          </CardContent>
                        </Card>
                      )
                    })
                  )}
                </div>
              </div>
            )
          })}
        </div></div>
      )}
    </div>
  )
}
