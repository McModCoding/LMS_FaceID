import { useEffect, useMemo, useState } from 'react'
import dayjs from 'dayjs'
import 'dayjs/locale/vi'
import { Calendar, ChevronLeft, ChevronRight, ListFilter, MapPin, Search, Table2 } from 'lucide-react'
import { timetableApi } from '../../api/timetable'
import { departmentsApi } from '../../api/departments'
import { TimetableSession } from '../../types/timetable'
import { Department } from '../../types/department'
import { getApiErrorMessage } from '@/lib/api-error'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RemoteSearchSelect } from '@/components/common/RemoteSearchSelect'
import { searchClasses, searchLecturers } from '@/lib/admin-search-options'

type ViewMode = 'list' | 'week'
const STATUS: Record<string, string> = { scheduled: 'Đã lên lịch', open: 'Đang mở', closed: 'Đã đóng', cancelled: 'Đã hủy' }
const time = (value: string) => value?.slice(0, 5) || '--:--'

export const AdminTimetablePage = () => {
  const [currentDate, setCurrentDate] = useState(new Date())
  const [sessions, setSessions] = useState<TimetableSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [filterError, setFilterError] = useState('')
  const [filterRetry, setFilterRetry] = useState(0)
  const [view, setView] = useState<ViewMode>('list')
  const [departmentId, setDepartmentId] = useState('all')
  const [lecturerId, setLecturerId] = useState('all')
  const [classId, setClassId] = useState('all')
  const [room, setRoom] = useState('')
  const [debouncedRoom, setDebouncedRoom] = useState('')
  const [departments, setDepartments] = useState<Department[]>([])
  const weekStart = useMemo(() => { const day = dayjs(currentDate).day(); return dayjs(currentDate).add(day === 0 ? -6 : 1 - day, 'day') }, [currentDate])
  const days = useMemo(() => Array.from({ length: 7 }, (_, index) => weekStart.add(index, 'day')), [weekStart])

  useEffect(() => {
    let active = true
    setFilterError('')
    void departmentsApi.getAll().then((result) => { if (active) setDepartments(result.filter((item) => item.is_active)) }).catch((err: unknown) => { if (active) setFilterError(getApiErrorMessage(err, 'Không thể tải danh sách khoa.')) })
    return () => { active = false }
  }, [filterRetry])
  useEffect(() => { const timer = window.setTimeout(() => setDebouncedRoom(room), 300); return () => window.clearTimeout(timer) }, [room])
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    void timetableApi.getAdminTimetable({ from_date: weekStart.format('YYYY-MM-DD'), to_date: weekStart.add(6, 'day').format('YYYY-MM-DD'), department_id: departmentId === 'all' ? undefined : Number(departmentId), lecturer_id: lecturerId === 'all' ? undefined : Number(lecturerId), class_id: classId === 'all' ? undefined : Number(classId), room: debouncedRoom.trim() || undefined }).then((result) => { if (active) setSessions(result.items) }).catch((err: unknown) => { if (active) setError(getApiErrorMessage(err, 'Không thể tải thời khóa biểu.')) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [weekStart, departmentId, lecturerId, classId, debouncedRoom, retry])
  const byDate = useMemo(() => sessions.reduce<Record<string, TimetableSession[]>>((result, session) => { (result[session.date] ||= []).push(session); return result }, {}), [sessions])

  return <Card><CardHeader className="gap-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle className="flex items-center gap-2"><Calendar className="h-5 w-5 text-primary" />Thời khóa biểu toàn trường</CardTitle><CardDescription className="mt-1">Lọc theo khoa, sau đó dùng danh sách để điều phối hoặc lưới tuần để rà soát lịch song song.</CardDescription></div><Tabs value={view} onValueChange={(value) => setView(value as ViewMode)}><TabsList><TabsTrigger value="list"><ListFilter className="mr-2 h-4 w-4" />Danh sách</TabsTrigger><TabsTrigger value="week"><Table2 className="mr-2 h-4 w-4" />Lưới tuần</TabsTrigger></TabsList></Tabs></div>
    <div className="flex flex-wrap items-start gap-2 rounded-lg border bg-muted/20 p-3"><Button variant="outline" size="sm" onClick={() => setCurrentDate(new Date())}>Hôm nay</Button><Button variant="outline" size="icon" className="h-9 w-9" onClick={() => setCurrentDate(weekStart.subtract(7, 'day').toDate())} aria-label="Tuần trước"><ChevronLeft className="h-4 w-4" /></Button><Button variant="outline" size="icon" className="h-9 w-9" onClick={() => setCurrentDate(weekStart.add(7, 'day').toDate())} aria-label="Tuần sau"><ChevronRight className="h-4 w-4" /></Button><span className="mr-2 text-sm font-medium">{weekStart.format('DD/MM/YYYY')} – {weekStart.add(6, 'day').format('DD/MM/YYYY')}</span><Filter value={departmentId} onChange={setDepartmentId} placeholder="Tất cả khoa" items={departments.map((item) => ({ value: String(item.id), label: `${item.code} · ${item.name}` }))} /><div className="w-full sm:w-[210px]"><RemoteSearchSelect value={lecturerId} onChange={setLecturerId} label="Giảng viên" emptyValue="all" emptyLabel="Tất cả giảng viên" search={searchLecturers} /></div><div className="w-full sm:w-[210px]"><RemoteSearchSelect value={classId} onChange={setClassId} label="Lớp học phần" emptyValue="all" emptyLabel="Tất cả lớp" search={searchClasses} /></div><div className="relative w-[150px]"><Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><Input aria-label="Lọc theo phòng học" value={room} onChange={(event) => setRoom(event.target.value)} className="pl-9" placeholder="Phòng học" /></div></div>
    {filterError && <div role="alert" className="rounded-md border p-3 text-sm"><p>Không tải đủ bộ lọc: {filterError}</p><Button variant="outline" size="sm" className="mt-2" onClick={() => setFilterRetry((value) => value + 1)}>Thử tải lại bộ lọc</Button></div>}
  </CardHeader><CardContent>{loading ? <div className="space-y-2"><Skeleton className="h-11 w-full" /><Skeleton className="h-11 w-full" /><Skeleton className="h-11 w-full" /></div> : error ? <div role="alert" className="rounded-lg border p-6 text-center"><p>Không thể tải thời khóa biểu: {error}</p><Button variant="outline" className="mt-3" onClick={() => setRetry((value) => value + 1)}>Thử lại</Button></div> : sessions.length === 0 ? <div className="rounded-lg border border-dashed py-14 text-center text-sm text-muted-foreground">Không có buổi học nào phù hợp. Hãy đổi tuần hoặc bớt điều kiện lọc.</div> : view === 'list' ? <ScheduleList sessions={sessions} /> : <div className="overflow-x-auto rounded-lg border"><div className="grid min-w-[980px] grid-cols-7 divide-x bg-card">{days.map((day) => <ScheduleDay key={day.format('YYYY-MM-DD')} day={day} sessions={byDate[day.format('YYYY-MM-DD')] || []} />)}</div></div>}</CardContent></Card>
}

function Filter({ value, onChange, placeholder, items }: { value: string; onChange: (value: string) => void; placeholder: string; items: { value: string; label: string }[] }) { return <Select value={value} onValueChange={onChange}><SelectTrigger aria-label={placeholder} className="w-[190px]"><SelectValue placeholder={placeholder} /></SelectTrigger><SelectContent><SelectItem value="all">{placeholder}</SelectItem>{items.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}</SelectContent></Select> }
function Status({ status }: { status: string }) { return <Badge variant={status === 'open' ? 'success' : status === 'cancelled' ? 'destructive' : 'secondary'}>{STATUS[status] || status}</Badge> }
function ScheduleList({ sessions }: { sessions: TimetableSession[] }) { return <div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[820px] text-sm"><thead className="border-b bg-muted/40 text-left text-muted-foreground"><tr><th className="p-3 font-medium">Ngày · giờ</th><th className="p-3 font-medium">Lớp · môn học</th><th className="p-3 font-medium">Giảng viên</th><th className="p-3 font-medium">Phòng</th><th className="p-3 font-medium">Trạng thái</th></tr></thead><tbody>{sessions.map((item) => <tr className="border-b last:border-0" key={item.session_id}><td className="whitespace-nowrap p-3"><div className="font-medium">{dayjs(item.date).locale('vi').format('ddd, DD/MM')}</div><div className="text-muted-foreground">{time(item.start_time)} – {time(item.end_time)}</div></td><td className="p-3"><div className="font-medium">{item.subject_name}</div><div className="text-muted-foreground">{item.class_code} · {item.subject_code}</div></td><td className="p-3">{item.lecturer_name || 'Chưa phân công'}</td><td className="p-3"><span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-muted-foreground" />{item.room}</span></td><td className="p-3"><Status status={item.status} /></td></tr>)}</tbody></table></div> }
function ScheduleDay({ day, sessions }: { day: dayjs.Dayjs; sessions: TimetableSession[] }) { const ordered = [...sessions].sort((a, b) => a.start_time.localeCompare(b.start_time)); return <section className="min-h-[420px]"><header className="border-b bg-muted/40 p-3 text-center"><div className="font-medium">{day.locale('vi').format('dddd')}</div><div className="text-xs text-muted-foreground">{day.format('DD/MM')}</div></header><div className="space-y-2 p-2">{ordered.length === 0 ? <p className="pt-8 text-center text-xs text-muted-foreground">Không có lịch</p> : ordered.map((item) => <article key={item.session_id} className="rounded-md border-l-4 border-l-primary bg-muted/20 p-2.5 text-xs"><div className="font-semibold text-primary">{time(item.start_time)} – {time(item.end_time)}</div><div className="mt-1 font-medium leading-snug">{item.subject_name}</div><div className="mt-1 text-muted-foreground">{item.class_code} · {item.room}</div><div className="mt-1 truncate text-muted-foreground">{item.lecturer_name || 'Chưa phân công'}</div></article>)}</div></section> }

export default AdminTimetablePage
