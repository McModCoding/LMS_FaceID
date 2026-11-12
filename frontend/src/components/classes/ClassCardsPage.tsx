import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, Search } from 'lucide-react'
import api from '@/api/client'
import { classesApi } from '@/api/classes'
import { RemoteState, Pagination } from '@/components/common/RemoteState'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { getApiErrorMessage } from '@/lib/api-error'
import type { Class, ClassStatus } from '@/types/class'

type Role = 'student' | 'lecturer'
type WorkItem = { title: string; context: string; class_id: number | null; link: string }
type WorkGroup = { title: string; items: WorkItem[] }

export function ClassCardsPage({ role }: { role: Role }) {
  const [classes, setClasses] = useState<Class[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<ClassStatus | ''>('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [groups, setGroups] = useState<WorkGroup[]>([])
  const [workLoading, setWorkLoading] = useState(true)
  const [workError, setWorkError] = useState('')
  const pageSize = 10

  useEffect(() => {
    const timer = window.setTimeout(() => { setQuery(search.trim()); setPage(1) }, 300)
    return () => window.clearTimeout(timer)
  }, [search])
  const loadClasses = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const result = await classesApi.getAll({ page, page_size: pageSize, q: query || undefined, status: status || undefined })
      setClasses(result.items); setTotal(result.total)
    } catch (cause) { setError(getApiErrorMessage(cause, 'Không tải được danh sách lớp học.')) }
    finally { setLoading(false) }
  }, [page, query, status])
  const loadWork = useCallback(async () => {
    setWorkLoading(true); setWorkError('')
    try { setGroups((await api.get<{ groups: WorkGroup[] }>('/me/dashboard')).data.groups) }
    catch (cause) { setWorkError(getApiErrorMessage(cause, 'Không tải được công việc của lớp.')) }
    finally { setWorkLoading(false) }
  }, [])
  useEffect(() => { void loadClasses() }, [loadClasses])
  useEffect(() => { void loadWork() }, [loadWork])

  function itemsForClass(cls: Class) {
    const relevantGroups = role === 'student'
      ? ['Kiểm tra cần theo dõi', 'Bài tập cần nộp', 'Phản hồi và thông báo chưa đọc', 'Lịch hôm nay', 'Cảnh báo chuyên cần']
      : ['Lịch hôm nay', 'Bài tập chờ chấm', 'Kiểm tra chờ chấm tự luận', 'Đơn xin vắng chờ duyệt', 'Cảnh báo chuyên cần']
    const byGroup = relevantGroups.map(name => {
      const group = groups.find(candidate => candidate.title === name)
      return (group?.items || []).filter(item => item.class_id === cls.id).map(item => ({ ...item, group: name }))
    })
    return [0, 1, 2].flatMap(index => byGroup.flatMap(group => group[index] ? [group[index]] : [])).slice(0, 3)
  }

  return <main className="min-w-0 space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-sm font-medium text-primary">{role === 'student' ? 'Không gian học tập' : 'Không gian giảng dạy'}</p><h1 className="mt-1 text-2xl font-semibold">{role === 'student' ? 'Lớp học của tôi' : 'Lớp học phụ trách'}</h1><p className="mt-1 text-sm text-muted-foreground">Chọn một lớp để xem nội dung và các hoạt động.</p></div>
      <div className="flex w-full flex-wrap gap-2 sm:w-auto"><div className="relative min-w-0 flex-1 sm:w-64"><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><Input aria-label="Tìm kiếm lớp học" placeholder="Tìm mã lớp, môn học..." className="pl-9" value={search} onChange={e => setSearch(e.target.value)} /></div><select aria-label="Trạng thái lớp" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={status} onChange={e => { setStatus(e.target.value as ClassStatus | ''); setPage(1) }}><option value="">Tất cả lớp</option><option value="active">Đang học</option><option value="closed">Đã kết thúc</option>{role === 'lecturer' && <option value="draft">Bản nháp</option>}</select></div>
    </div>
    <RemoteState loading={false} error={error} onRetry={loadClasses} />
    {loading ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label="Đang tải lớp học">{[1, 2, 3].map(i => <Skeleton key={i} className="h-80 rounded-xl" />)}</div> : !error && classes.length === 0 ? <RemoteState loading={false} empty={query || status ? 'Không tìm thấy lớp phù hợp. Hãy thử đổi từ khóa hoặc bộ lọc.' : role === 'student' ? 'Bạn chưa được ghi danh vào lớp. Hãy liên hệ giảng viên hoặc quản trị viên.' : 'Bạn chưa được phân công lớp. Hãy liên hệ quản trị viên.'} /> : !error && <>
      {workError && <div role="alert" className="flex flex-wrap items-center gap-2 rounded-lg border p-3 text-sm"><span>{workError}</span><Button variant="outline" size="sm" onClick={loadWork}>Thử lại</Button></div>}
      <div className="grid items-stretch gap-4 md:grid-cols-2 xl:grid-cols-3">{classes.map(cls => {
        const items = itemsForClass(cls)
        const banner = ['course-banner-blue', 'course-banner-teal', 'course-banner-violet'][cls.id % 3]
        return <Card key={cls.id} className="flex min-w-0 flex-col overflow-hidden rounded-xl shadow-sm">
          <div className={`${banner} relative min-h-40 overflow-hidden p-5`}><div className="course-banner-decoration" aria-hidden="true" /><div className="relative"><p className="text-sm font-medium opacity-90">{cls.code} · {cls.subject_code || 'Môn học'}</p><h2 className="mt-2 min-h-14 overflow-hidden text-xl font-semibold leading-7 [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]" title={cls.subject_name || cls.code}><Link className="hover:underline" to={`/${role}/classes/${cls.id}`}>{cls.subject_name || cls.code}</Link></h2><p className="mt-2 truncate text-sm" title={cls.semester_name || ''}>{cls.semester_name || 'Chưa cập nhật học kỳ'}</p><p className="truncate text-sm opacity-90" title={cls.lecturer_name || ''}>Giảng viên: {cls.lecturer_name || 'Chưa phân công'}</p><p className="mt-2 text-xs font-medium">{cls.status === 'closed' ? 'Đã kết thúc' : cls.status === 'draft' ? 'Nháp' : role === 'student' ? 'Đang học' : 'Đang hoạt động'}</p></div></div>
          <div className="flex flex-1 flex-col gap-3 p-5"><div className="flex items-center justify-between gap-2"><h3 className="font-semibold">{role === 'student' ? 'Sắp đến hạn & thông báo' : 'Công việc cần xử lý'}</h3></div>
            {workLoading ? <div aria-label="Đang tải công việc" className="space-y-2"><Skeleton className="h-8 w-full" /><Skeleton className="h-8 w-full" /></div> : workError ? <p className="text-sm text-muted-foreground">Chưa tải được công việc. Dùng nút thử lại phía trên.</p> : items.length ? <ul className="space-y-2">{items.map((item, index) => <li key={`${item.link}-${index}`} className="rounded-md border bg-secondary/40 p-2.5"><p className="text-xs font-medium text-muted-foreground">{item.group}</p><Link className="mt-0.5 block break-words text-sm font-medium text-primary hover:underline" to={item.link}>{item.title}</Link></li>)}</ul> : <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">Chưa có công việc trong các nhóm được hiển thị. Mở lớp để xem học liệu và thông báo.</p>}
            <div className="mt-auto flex items-center justify-between gap-2 border-t pt-3"><Link className="text-sm text-primary hover:underline" to={`/${role}/classes/${cls.id}?tab=announcements`}>Thông báo lớp</Link><Button asChild><Link to={`/${role}/classes/${cls.id}`}><BookOpen className="mr-2 h-4 w-4" />{cls.status === 'closed' ? 'Xem lịch sử' : 'Vào lớp'}</Link></Button></div>
          </div>
        </Card>
      })}</div>
      <Pagination page={page} total={total} pageSize={pageSize} loading={loading} onChange={setPage} />
    </>}
  </main>
}
