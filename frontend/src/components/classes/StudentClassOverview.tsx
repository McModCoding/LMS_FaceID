import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { BookOpen, CalendarDays, ClipboardList, Megaphone, UserRound } from 'lucide-react'
import api from '@/api/client'
import { classesApi } from '@/api/classes'
import { learningApi, type Announcement } from '@/api/learning'
import { materialsApi, type Material } from '@/api/materials'
import { RemoteState } from '@/components/common/RemoteState'
import { HeroSection } from '@/components/common/HeroSection'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getApiErrorMessage } from '@/lib/api-error'
import type { Class } from '@/types/class'
import type { Schedule } from '@/types/schedule'

type WorkItem = { title: string; class_id: number | null; link: string }
type WorkGroup = { title: string; items: WorkItem[] }
type Dashboard = { groups: WorkGroup[] }

function useResource<T>(load: () => Promise<T>, fallback: string) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  useEffect(() => {
    let active = true
    setLoading(true); setError(''); setData(null)
    load().then(result => { if (active) setData(result) })
      .catch(cause => { if (active) setError(getApiErrorMessage(cause, fallback)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [load, fallback, version])
  return { data, loading, error, retry: () => setVersion(v => v + 1) }
}

function Section({ title, description, children, className = '' }: { title: string; description: string; children: ReactNode; className?: string }) {
  return <Card className={`min-w-0 ${className}`}><CardHeader className="pb-3"><CardTitle className="text-base leading-6">{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader><CardContent>{children}</CardContent></Card>
}
function RowIcon({ children }: { children: ReactNode }) {
  return <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary" aria-hidden="true">{children}</span>
}
const weekdays = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ nhật']
const dateLabel = (date: string) => date.split('-').reverse().join('/')

export function StudentClassOverview({ classData }: { classData: Class }) {
  const location = useLocation()
  const loadWork = useCallback(() => api.get<Dashboard>('/me/dashboard').then(r => r.data), [])
  const loadSchedules = useCallback(() => classesApi.getSchedules(classData.id), [classData.id])
  const loadMaterials = useCallback(() => materialsApi.list(classData.id, 1).then(r => r.items), [classData.id])
  const loadNotices = useCallback(() => learningApi.announcements(classData.id), [classData.id])
  const work = useResource<Dashboard>(loadWork, 'Không tải được việc học.')
  const schedules = useResource<Schedule[]>(loadSchedules, 'Không tải được lịch học.')
  const materials = useResource<Material[]>(loadMaterials, 'Không tải được học liệu.')
  const notices = useResource<Announcement[]>(loadNotices, 'Không tải được thông báo lớp.')
  const route = (tab: string) => `${location.pathname}?tab=${tab}`
  const groups = ['Kiểm tra cần theo dõi', 'Bài tập cần nộp', 'Cảnh báo chuyên cần']
    .map(title => ({ title, items: (work.data?.groups.find(group => group.title === title)?.items || []).filter(item => item.class_id === classData.id) }))
  const tasks = [0, 1, 2].flatMap(index => groups.flatMap(group => group.items[index] ? [{ ...group.items[index], group: group.title }] : [])).slice(0, 3)
  const isClosed = classData.status === 'closed'
  const statusLabel = isClosed ? 'Đã kết thúc' : classData.status === 'draft' ? 'Nháp' : 'Đang học'
  return (
    <div className="space-y-4 sm:space-y-5">
      <HeroSection
        tag={`${classData.code} · ${statusLabel}`}
        title={classData.subject_name || classData.code}
        description={`Giảng viên: ${classData.lecturer_name || 'Chưa phân công'} · ${classData.semester_name || 'Học kỳ hiện tại'}`}
        variant={isClosed ? 'warm' : 'blue'}
        action={{ label: 'Xem lịch lớp', href: route('schedules') }}
      />
    <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <Section title="Việc học tiếp theo" description="Các hoạt động cần quan tâm" className="lg:order-1">
        <RemoteState loading={work.loading} error={work.error} onRetry={work.retry} />
        {!work.loading && !work.error && (tasks.length ? <ul className="divide-y">{tasks.map((item, index) => <li key={`${item.group}-${item.link}-${index}`} className="flex min-w-0 items-start gap-3 py-3 first:pt-0 last:pb-0"><RowIcon><ClipboardList className="h-4 w-4" /></RowIcon><div className="min-w-0 flex-1"><p className="break-words font-medium">{item.title}</p><p className="mt-1 text-xs text-muted-foreground">{item.group}</p><Link className="mt-2 inline-block text-sm font-medium text-primary hover:underline" to={item.link}>{item.link.startsWith('/student/exams/') ? 'Tiếp tục làm bài' : item.group === 'Bài tập cần nộp' ? 'Mở mục bài tập' : item.group === 'Kiểm tra cần theo dõi' ? 'Mở mục kiểm tra' : 'Xem chuyên cần'}</Link></div></li>)}</ul> : <p className="text-sm text-muted-foreground">{isClosed ? 'Lớp đã kết thúc. Bạn có thể xem lại học liệu và kết quả trong các mục của lớp.' : 'Chưa có việc học trong các nhóm được hiển thị. Hãy xem học liệu hoặc thông báo của lớp.'}</p>)}
      </Section>
      <Section title="Học liệu gần đây" description="Tài liệu và liên kết dành cho lớp" className="lg:order-3">
        <RemoteState loading={materials.loading} error={materials.error} onRetry={materials.retry} />
        {!materials.loading && !materials.error && (materials.data?.length ? <ul className="divide-y">{materials.data.slice(0, 3).map(item => <li key={item.id} className="flex min-w-0 items-start gap-3 py-3 first:pt-0 last:pb-0"><RowIcon><BookOpen className="h-4 w-4" /></RowIcon><div className="min-w-0 flex-1"><p className="break-words font-medium">{item.title}</p><p className="mt-1 text-xs text-muted-foreground">{item.url ? 'Liên kết tham khảo' : 'Tài liệu tải về'}</p></div></li>)}</ul> : <p className="text-sm text-muted-foreground">Chưa có học liệu. Giảng viên sẽ đăng tài liệu tại đây.</p>)}
        {!materials.loading && !materials.error && !!materials.data?.length && <Button asChild variant="outline" size="sm" className="mt-4"><Link to={route('materials')}>Xem mục học liệu</Link></Button>}
      </Section>
      <Section title="Thông tin lớp" description="Lịch và người phụ trách" className="lg:order-2">
        <div className="space-y-4"><div className="flex items-start gap-3"><RowIcon><CalendarDays className="h-4 w-4" /></RowIcon><div className="min-w-0 flex-1"><p className="font-medium">Lịch định kỳ</p><RemoteState loading={schedules.loading} error={schedules.error} onRetry={schedules.retry} />{!schedules.loading && !schedules.error && (schedules.data?.length ? <ul className="mt-1 space-y-2 text-sm text-muted-foreground">{schedules.data.slice(0, 2).map(schedule => <li key={schedule.id} className="break-words">{weekdays[schedule.weekday] || 'Ngày chưa rõ'} · {schedule.start_time.slice(0, 5)}–{schedule.end_time.slice(0, 5)} · {schedule.room}<span className="block text-xs">Từ {dateLabel(schedule.start_date)} đến {dateLabel(schedule.end_date)}</span></li>)}</ul> : <p className="mt-1 text-sm text-muted-foreground">Chưa có lịch định kỳ. Xem danh sách buổi học để biết lịch chi tiết.</p>)}</div></div><div className="flex items-start gap-3 border-t pt-4"><RowIcon><UserRound className="h-4 w-4" /></RowIcon><div className="min-w-0"><p className="break-words font-medium">{classData.lecturer_name || 'Chưa phân công'}</p><p className="text-xs text-muted-foreground">Giảng viên phụ trách</p></div></div><Button asChild variant="outline" size="sm"><Link to={route('schedules')}>Xem lịch và buổi học</Link></Button><details className="border-t pt-3 text-sm"><summary className="cursor-pointer font-medium">Quy định chuyên cần</summary><p className="mt-2 text-muted-foreground">Đi trễ sau {classData.late_after_min} phút · Tính vắng sau {classData.absent_after_min} phút · Cảnh báo từ {classData.attendance_warning_absences} buổi vắng.</p><p className="mt-2 text-muted-foreground">Trọng số: có mặt {classData.weight_present} · trễ {classData.weight_late} · có phép {classData.weight_excused}.</p></details></div>
      </Section>
      <Section title="Thông báo lớp" description="Thông báo ghim và cập nhật từ lớp" className="lg:order-4">
        <RemoteState loading={notices.loading} error={notices.error} onRetry={notices.retry} />
        {!notices.loading && !notices.error && (notices.data?.length ? <ul className="divide-y">{notices.data.slice(0, 3).map(item => <li key={item.id} className="flex min-w-0 items-start gap-3 py-3 first:pt-0 last:pb-0"><RowIcon><Megaphone className="h-4 w-4" /></RowIcon><div className="min-w-0 flex-1"><p className="break-words font-medium">{item.title}{item.is_pinned && <span className="ml-2 text-xs text-primary">Đã ghim</span>}</p><p className="mt-1 break-words text-xs text-muted-foreground">{item.author_name}</p></div></li>)}</ul> : <p className="text-sm text-muted-foreground">Chưa có thông báo trong lớp.</p>)}
        {!notices.loading && !notices.error && !!notices.data?.length && <Button asChild variant="outline" size="sm" className="mt-4"><Link to={route('announcements')}>Xem mục thông báo</Link></Button>}
      </Section>
      </div>
    </div>
  )
}
