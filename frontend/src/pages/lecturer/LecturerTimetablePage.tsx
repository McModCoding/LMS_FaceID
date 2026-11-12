import { useState, useEffect, useCallback } from 'react'
import dayjs from 'dayjs'
import { Calendar } from 'lucide-react'
import { getApiErrorMessage } from '@/lib/api-error'
import { RemoteState } from '@/components/common/RemoteState'

import { TimetableSession } from '../../types/timetable'
import { timetableApi } from '../../api/timetable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { WeeklyTimetable } from '../../components/common/WeeklyTimetable'

export const LecturerTimetablePage = () => {
  const [currentDate, setCurrentDate] = useState<Date>(new Date())
  const [sessions, setSessions] = useState<TimetableSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchTimetable = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const currentDayOfWeek = dayjs(currentDate).day()
      const mondayOffset = currentDayOfWeek === 0 ? -6 : 1 - currentDayOfWeek
      const monday = dayjs(currentDate).add(mondayOffset, 'day')
      const sunday = monday.add(6, 'day')

      const res = await timetableApi.getMyTimetable({
        from_date: monday.format('YYYY-MM-DD'),
        to_date: sunday.format('YYYY-MM-DD'),
      })
      setSessions(res.items)
    } catch (error: unknown) {
      setError(getApiErrorMessage(error, 'Không thể tải thời khóa biểu. Hãy kiểm tra kết nối và thử lại.'))
    } finally {
      setLoading(false)
    }
  }, [currentDate])

  useEffect(() => {
    fetchTimetable()
  }, [fetchTimetable])

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-center gap-2">
          <Calendar className="h-5 w-5 text-primary" />
          <CardTitle>Thời khóa biểu giảng dạy</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {error ? <RemoteState loading={false} error={error} onRetry={fetchTimetable} /> : <WeeklyTimetable
          sessions={sessions}
          currentDate={currentDate}
          onDateChange={setCurrentDate}
          loading={loading}
          showLecturer={false}
        />}
      </CardContent>
    </Card>
  )
}

export default LecturerTimetablePage
