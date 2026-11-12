import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { Calendar, Clock, MapPin, BookOpen, PlayCircle, CheckCircle2, XCircle } from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '../../auth/AuthContext'
import { TimetableSession } from '../../types/timetable'
import { timetableApi } from '../../api/timetable'

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export const LecturerDashboardPage = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [todaySessions, setTodaySessions] = useState<TimetableSession[]>([])
  const [loading, setLoading] = useState(true)

  const todayStr = dayjs().format('YYYY-MM-DD')
  const displayDate = dayjs().format('dddd, [ngày] DD/MM/YYYY')

  useEffect(() => {
    const fetchToday = async () => {
      setLoading(true)
      try {
        const res = await timetableApi.getMyTimetable({
          from_date: todayStr,
          to_date: todayStr,
        })
        setTodaySessions(res.items)
      } catch (error: unknown) {
        const msg = (error as any)?.response?.data?.detail?.message || 'Không thể tải lịch hôm nay'
        toast.error(msg)
      } finally {
        setLoading(false)
      }
    }
    fetchToday()
  }, [todayStr])

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'scheduled':
        return <Badge variant="outline">Chưa mở</Badge>
      case 'open':
        return (
          <Badge variant="success" className="flex items-center gap-1">
            <PlayCircle className="h-3 w-3" /> Đang mở
          </Badge>
        )
      case 'closed':
        return (
          <Badge variant="secondary" className="flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" /> Đã đóng
          </Badge>
        )
      case 'cancelled':
        return (
          <Badge variant="destructive" className="flex items-center gap-1">
            <XCircle className="h-3 w-3" /> Đã hủy
          </Badge>
        )
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  return (
    <div className="space-y-6">

      <Card className="border-primary/20 bg-secondary/60">
        <CardHeader>
          <CardTitle className="text-2xl">Xin chào, Giảng viên {user?.username}!</CardTitle>
          <CardDescription className="capitalize">
            Hôm nay là {displayDate}
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Today's schedule section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Lịch giảng dạy hôm nay</h2>
          </div>
          <Button variant="outline" size="sm" onClick={() => navigate('/lecturer/timetable')}>
            Xem toàn bộ tuần
          </Button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <Skeleton className="h-36 w-full" />
            <Skeleton className="h-36 w-full" />
          </div>
        ) : todaySessions.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground space-y-2">
              <Calendar className="h-10 w-10 mx-auto text-muted-foreground/40" />
              <p className="font-medium">Hôm nay bạn không có buổi giảng dạy nào.</p>
              <p className="text-xs">Bạn có thể kiểm tra thời khóa biểu tuần để chuẩn bị cho các buổi học tiếp theo.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {todaySessions.map((s) => (
              <Card
                key={s.session_id}
                className={cn(
                  'transition-all hover:border-primary/50',
                  s.status === 'cancelled' && 'opacity-60 bg-muted/40'
                )}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-bold text-base text-primary">{s.class_code}</span>
                    {getStatusBadge(s.status)}
                  </div>
                  <CardTitle className="text-sm font-semibold">{s.subject_name}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm pt-0">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Clock className="h-4 w-4 text-primary shrink-0" />
                    <span>
                      {s.start_time.slice(0, 5)} - {s.end_time.slice(0, 5)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <MapPin className="h-4 w-4 text-primary shrink-0" />
                    <span>Phòng: <strong className="text-foreground">{s.room}</strong></span>
                  </div>

                  <div className="pt-2 border-t flex justify-end">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs"
                      onClick={() => navigate(`/lecturer/classes/${s.class_id}`)}
                    >
                      <BookOpen className="mr-1.5 h-3.5 w-3.5" /> Chi tiết lớp
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default LecturerDashboardPage
