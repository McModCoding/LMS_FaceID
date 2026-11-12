import { ReactNode, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, GraduationCap, Mail, Phone, UserRound } from 'lucide-react'
import { lecturersApi } from '../../api/lecturers'
import { classesApi } from '../../api/classes'
import { Lecturer } from '../../types/lecturer'
import { ClassListResponse } from '../../types/class'
import { getApiErrorMessage } from '@/lib/api-error'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

export default function LecturerProfilePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const lecturerId = Number(id)
  const [lecturer, setLecturer] = useState<Lecturer | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [page, setPage] = useState(1)
  const [classes, setClasses] = useState<ClassListResponse | null>(null)
  const [classLoading, setClassLoading] = useState(true)
  const [classError, setClassError] = useState('')
  const [classRetry, setClassRetry] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true); setError(''); setLecturer(null)
    if (!Number.isInteger(lecturerId) || lecturerId < 1) { setError('Mã giảng viên không hợp lệ.'); setLoading(false); return }
    void lecturersApi.getById(lecturerId).then((value) => { if (active) setLecturer(value) }).catch((err: unknown) => {
      if (active) setError(getApiErrorMessage(err, 'Không thể tải hồ sơ giảng viên.'))
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [lecturerId, retry])

  useEffect(() => {
    if (!Number.isInteger(lecturerId) || lecturerId < 1) return
    let active = true
    setClassLoading(true); setClassError('')
    void classesApi.getAll({ lecturer_id: lecturerId, page, page_size: 10 }).then((value) => { if (active) setClasses(value) }).catch((err: unknown) => {
      if (active) { setClasses(null); setClassError(getApiErrorMessage(err, 'Không thể tải danh sách lớp.')) }
    }).finally(() => { if (active) setClassLoading(false) })
    return () => { active = false }
  }, [lecturerId, page, classRetry])

  if (loading) return <Card><CardContent className="space-y-3 p-6"><Skeleton className="h-8 w-64" /><Skeleton className="h-28 w-full" /></CardContent></Card>
  if (!lecturer) return <div role="alert" className="space-y-3"><p>{error}</p><Button variant="outline" onClick={() => setRetry((value) => value + 1)}>Thử lại</Button><Button variant="ghost" onClick={() => navigate('/admin/lecturers')}>Quay lại danh sách giảng viên</Button></div>
  const accountStatus = lecturer.user_is_active === true ? 'Đang hoạt động' : lecturer.user_is_active === false ? 'Đang khóa' : 'Chưa có thông tin'
  return <div className="space-y-4"><Button variant="ghost" onClick={() => navigate('/admin/lecturers')}><ArrowLeft className="mr-2 h-4 w-4" />Quay lại danh sách giảng viên</Button>
    <Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div className="flex gap-3"><div className="grid h-11 w-11 place-items-center rounded-full bg-primary/10 text-primary"><UserRound className="h-5 w-5" /></div><div><CardTitle>{lecturer.full_name}</CardTitle><CardDescription>{lecturer.code} · {lecturer.type === 'full_time' ? 'Giảng viên cơ hữu' : 'Giảng viên thỉnh giảng'}</CardDescription></div></div><Badge variant={lecturer.user_is_active === true ? 'success' : 'secondary'}>{accountStatus}</Badge></div></CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><Info title="Khoa" value={lecturer.department_name || 'Chưa gán khoa'} href={lecturer.department_id ? `/admin/departments/${lecturer.department_id}` : undefined} icon={<GraduationCap className="h-4 w-4" />} /><Info title="Học vị" value={lecturer.degree || 'Chưa cập nhật'} /><Info title="Email" value={lecturer.email || 'Chưa cập nhật'} icon={<Mail className="h-4 w-4" />} /><Info title="Số điện thoại" value={lecturer.phone || 'Chưa cập nhật'} icon={<Phone className="h-4 w-4" />} /></CardContent></Card>
    <Card><CardHeader><CardTitle className="text-base">Lớp học phần được phân công</CardTitle><CardDescription>Danh sách theo giảng viên phụ trách hiện tại của từng lớp.</CardDescription></CardHeader><CardContent>
      {classLoading ? <div className="space-y-2"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div> : classError ? <div role="alert"><p>{classError}</p><Button className="mt-2" variant="outline" size="sm" onClick={() => setClassRetry((value) => value + 1)}>Thử lại</Button></div> : !classes?.items.length ? <p className="text-sm text-muted-foreground">Chưa có lớp học phần được phân công.</p> : <><ul className="divide-y">{classes.items.map((item) => <li key={item.id} className="py-3"><Link to={`/admin/classes/${item.id}`} className="font-medium text-primary underline-offset-4 hover:underline">{item.subject_name || item.code}</Link><p className="text-sm text-muted-foreground">{item.code} · {item.semester_name}</p></li>)}</ul><div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-sm"><span>Tổng cộng: {classes.total} lớp học phần</span><div className="flex items-center gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Trước</Button><span>Trang {page} / {Math.max(1, Math.ceil(classes.total / 10))}</span><Button variant="outline" size="sm" disabled={page * 10 >= classes.total} onClick={() => setPage(page + 1)}>Sau</Button></div></div></>}
    </CardContent></Card></div>
}
function Info({ title, value, icon, href }: { title: string; value: string; icon?: ReactNode; href?: string }) { return <div className="rounded-lg border p-3"><p className="flex items-center gap-2 text-xs text-muted-foreground">{icon}{title}</p>{href ? <Link to={href} className="mt-1 block break-words text-sm font-medium text-primary underline-offset-4 hover:underline">{value}</Link> : <p className="mt-1 break-words text-sm font-medium">{value}</p>}</div> }
