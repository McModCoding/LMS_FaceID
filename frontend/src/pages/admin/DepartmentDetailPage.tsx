import { ReactNode, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, BookOpen, Building2, GraduationCap, Users } from 'lucide-react'
import { departmentsApi } from '../../api/departments'
import { studentsApi } from '../../api/students'
import { lecturersApi } from '../../api/lecturers'
import { subjectsApi } from '../../api/subjects'
import { classesApi } from '../../api/classes'
import { Department } from '../../types/department'
import { Student } from '../../types/student'
import { Lecturer } from '../../types/lecturer'
import { Subject } from '../../types/subject'
import { Class } from '../../types/class'
import { getApiErrorMessage } from '@/lib/api-error'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const PAGE_SIZE = 20
type PageResult<T> = { items: T[]; total: number }
const loadStudents = (id: number, page: number) => studentsApi.getAll({ page, page_size: PAGE_SIZE, department_id: id })
const loadLecturers = (id: number, page: number) => lecturersApi.getAll({ page, page_size: PAGE_SIZE, department_id: id })
const loadClasses = (id: number, page: number) => classesApi.getAll({ page, page_size: PAGE_SIZE, department_id: id })

function useDepartmentPage<T>(departmentId: number, load: (id: number, page: number) => Promise<PageResult<T>>) {
  const [page, setPage] = useState(1)
  const [result, setResult] = useState<PageResult<T> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => { setPage(1) }, [departmentId])
  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    setResult(null)
    if (!Number.isInteger(departmentId) || departmentId < 1) {
      setError('Mã khoa không hợp lệ.')
      setLoading(false)
      return
    }
    void load(departmentId, page).then((data) => { if (active) setResult(data) }).catch((err: unknown) => {
      if (active) { setResult(null); setError(getApiErrorMessage(err, 'Không thể tải danh sách.')) }
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [departmentId, page, retry, load])
  return { page, setPage, result, loading, error, retry: () => setRetry((value) => value + 1) }
}

export default function DepartmentDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const departmentId = Number(id)
  const [department, setDepartment] = useState<Department | null>(null)
  const [subjects, setSubjects] = useState<Subject[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [subjectError, setSubjectError] = useState('')
  const [retry, setRetry] = useState(0)
  const [subjectPage, setSubjectPage] = useState(1)
  const students = useDepartmentPage<Student>(departmentId, loadStudents)
  const lecturers = useDepartmentPage<Lecturer>(departmentId, loadLecturers)
  const classes = useDepartmentPage<Class>(departmentId, loadClasses)

  useEffect(() => {
    let active = true
    setSubjectPage(1)
    setLoading(true); setError(''); setSubjectError(''); setDepartment(null); setSubjects(null)
    if (!Number.isInteger(departmentId) || departmentId < 1) { setError('Mã khoa không hợp lệ.'); setLoading(false); return }
    void departmentsApi.getById(departmentId).then((value) => { if (active) setDepartment(value) }).catch((err: unknown) => {
      if (active) setError(getApiErrorMessage(err, 'Không thể tải thông tin khoa.'))
    }).finally(() => { if (active) setLoading(false) })
    void subjectsApi.getAll(undefined, departmentId).then((value) => { if (active) setSubjects(value) }).catch((err: unknown) => {
      if (active) setSubjectError(getApiErrorMessage(err, 'Không thể tải danh sách môn học.'))
    })
    return () => { active = false }
  }, [departmentId, retry])

  if (loading) return <Card><CardContent className="space-y-3 p-6"><Skeleton className="h-8 w-64" /><Skeleton className="h-40 w-full" /></CardContent></Card>
  if (!department) return <div role="alert" className="space-y-3"><p>{error || 'Không thể tải thông tin khoa.'}</p><Button variant="outline" onClick={() => setRetry((value) => value + 1)}>Thử lại</Button><Button variant="ghost" onClick={() => navigate('/admin/departments')}>Quay lại danh sách khoa</Button></div>

  const subjectItems = subjects?.slice((subjectPage - 1) * PAGE_SIZE, subjectPage * PAGE_SIZE) || []
  return <div className="space-y-4">
    <Button variant="ghost" onClick={() => navigate('/admin/departments')}><ArrowLeft className="mr-2 h-4 w-4" />Quay lại danh sách khoa</Button>
    <Card><CardHeader><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><Building2 className="h-6 w-6 text-primary" /><div><CardTitle>{department.name}</CardTitle><p className="text-sm text-muted-foreground">Mã khoa: {department.code}</p></div></div><Badge variant={department.is_active ? 'success' : 'secondary'}>{department.is_active ? 'Đang sử dụng' : 'Ngừng sử dụng'}</Badge></div></CardHeader>
      <CardContent><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Metric label="Giảng viên" value={lecturers.result?.total} icon={<Users className="h-4 w-4" />} /><Metric label="Sinh viên" value={students.result?.total} icon={<GraduationCap className="h-4 w-4" />} /><Metric label="Môn học" value={subjects?.length} icon={<BookOpen className="h-4 w-4" />} /><Metric label="Lớp học phần" value={classes.result?.total} icon={<BookOpen className="h-4 w-4" />} /></div></CardContent></Card>
    <Tabs defaultValue="lecturers"><TabsList className="max-w-full overflow-x-auto"><TabsTrigger value="lecturers">Giảng viên</TabsTrigger><TabsTrigger value="students">Sinh viên</TabsTrigger><TabsTrigger value="subjects">Môn học</TabsTrigger><TabsTrigger value="classes">Lớp học phần</TabsTrigger></TabsList>
      <TabsContent value="lecturers"><RecordCard {...lecturers} empty="Chưa có giảng viên được gán khoa này." items={(lecturers.result?.items || []).map((item) => ({ id: item.id, title: item.full_name, subtitle: `${item.code} · ${item.email || 'Chưa có email'}`, href: `/admin/lecturers/${item.id}` }))} /></TabsContent>
      <TabsContent value="students"><RecordCard {...students} empty="Chưa có sinh viên được gán khoa này." items={(students.result?.items || []).map((item) => ({ id: item.id, title: item.full_name, subtitle: `${item.student_code} · ${item.admin_class || 'Chưa có lớp hành chính'}`, href: `/admin/students/${item.id}` }))} /></TabsContent>
      <TabsContent value="subjects"><RecordCard page={subjectPage} setPage={setSubjectPage} loading={!subjects && !subjectError} error={subjectError} retry={() => setRetry((value) => value + 1)} total={subjects?.length} empty="Chưa có môn học được gán khoa này." items={subjectItems.map((item) => ({ id: item.id, title: item.name, subtitle: `${item.code} · ${item.credits} tín chỉ` }))} /></TabsContent>
      <TabsContent value="classes"><RecordCard {...classes} empty="Chưa có lớp học phần thuộc khoa này." items={(classes.result?.items || []).map((item) => ({ id: item.id, title: item.subject_name || item.code, subtitle: `${item.code} · ${item.semester_name || 'Chưa có học kỳ'}`, href: `/admin/classes/${item.id}` }))} /></TabsContent>
    </Tabs>
  </div>
}

function Metric({ label, value, icon }: { label: string; value?: number; icon: ReactNode }) {
  return <div className="rounded-lg border p-3"><p className="flex items-center gap-2 text-xs text-muted-foreground">{icon}{label}</p><p className="mt-1 text-2xl font-semibold">{value ?? '—'}</p></div>
}
type RecordItem = { id: number; title: string; subtitle: string; href?: string }
function RecordCard({ items, empty, loading, error, retry, page, setPage, total, result }: { items: RecordItem[]; empty: string; loading: boolean; error: string; retry: () => void; page: number; setPage: (page: number) => void; total?: number; result?: PageResult<unknown> | null }) {
  const count = total ?? result?.total ?? 0
  return <Card className="mt-4"><CardContent className="p-0">{loading ? <div className="space-y-2 p-4"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div> : error ? <div role="alert" className="space-y-2 p-4"><p>{error}</p><Button variant="outline" size="sm" onClick={retry}>Thử lại</Button></div> : items.length === 0 ? <p className="p-8 text-center text-sm text-muted-foreground">{empty}</p> : <><ul className="divide-y">{items.map((item) => <li key={item.id} className="p-3">{item.href ? <Link className="font-medium text-primary underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2" to={item.href}>{item.title}</Link> : <p className="font-medium">{item.title}</p>}<p className="text-sm text-muted-foreground">{item.subtitle}</p></li>)}</ul><div className="flex flex-wrap items-center justify-between gap-2 border-t p-3 text-sm"><span>Tổng cộng: {count}</span><div className="flex items-center gap-2"><Button variant="outline" size="sm" onClick={() => setPage(page - 1)} disabled={page <= 1}>Trước</Button><span>Trang {page} / {Math.max(1, Math.ceil(count / PAGE_SIZE))}</span><Button variant="outline" size="sm" onClick={() => setPage(page + 1)} disabled={page * PAGE_SIZE >= count}>Sau</Button></div></div></>}</CardContent></Card>
}
