import { ReactNode, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, GraduationCap, Mail, Phone, UserRound } from 'lucide-react'
import { studentsApi } from '../../api/students'
import { Student } from '../../types/student'
import { getApiErrorMessage } from '@/lib/api-error'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

const studentStatus: Record<string, string> = { studying: 'Đang học', suspended: 'Bảo lưu', graduated: 'Đã tốt nghiệp' }
export default function StudentProfilePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const studentId = Number(id)
  const [student, setStudent] = useState<Student | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let active = true
    setLoading(true); setError(''); setStudent(null)
    if (!Number.isInteger(studentId) || studentId < 1) { setError('Mã sinh viên không hợp lệ.'); setLoading(false); return }
    void studentsApi.getById(studentId).then((value) => { if (active) setStudent(value) }).catch((err: unknown) => {
      if (active) setError(getApiErrorMessage(err, 'Không thể tải hồ sơ sinh viên.'))
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [studentId, retry])
  if (loading) return <Card><CardContent className="space-y-3 p-6"><Skeleton className="h-8 w-64" /><Skeleton className="h-28 w-full" /></CardContent></Card>
  if (!student) return <div role="alert" className="space-y-3"><p>{error}</p><Button variant="outline" onClick={() => setRetry((value) => value + 1)}>Thử lại</Button><Button variant="ghost" onClick={() => navigate('/admin/students')}>Quay lại danh sách sinh viên</Button></div>
  const accountStatus = student.user_is_active === true ? 'Đang hoạt động' : student.user_is_active === false ? 'Đang khóa' : 'Chưa có thông tin'
  return <div className="space-y-4"><Button variant="ghost" onClick={() => navigate('/admin/students')}><ArrowLeft className="mr-2 h-4 w-4" />Quay lại danh sách sinh viên</Button><Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div className="flex gap-3"><div className="grid h-11 w-11 place-items-center rounded-full bg-primary/10 text-primary"><UserRound className="h-5 w-5" /></div><div><CardTitle>{student.full_name}</CardTitle><CardDescription>{student.student_code} · {student.admin_class || 'Chưa có lớp hành chính'}</CardDescription></div></div><Badge variant={student.status === 'studying' ? 'success' : 'secondary'}>{studentStatus[student.status] || student.status}</Badge></div></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><Info title="Khoa" value={student.department_name || 'Chưa gán khoa'} href={student.department_id ? `/admin/departments/${student.department_id}` : undefined} icon={<GraduationCap className="h-4 w-4" />} /><Info title="Email" value={student.email || 'Chưa cập nhật'} icon={<Mail className="h-4 w-4" />} /><Info title="Số điện thoại" value={student.phone || 'Chưa cập nhật'} icon={<Phone className="h-4 w-4" />} /><Info title="Ngày sinh" value={student.dob || 'Chưa cập nhật'} /><Info title="Giới tính" value={student.gender || 'Chưa cập nhật'} /><Info title="Tài khoản" value={accountStatus} /></CardContent></Card><Card><CardHeader><CardTitle className="text-base">Thông tin liên quan</CardTitle><CardDescription>Chưa thể xem danh sách lớp học phần của sinh viên tại đây.</CardDescription></CardHeader></Card></div>
}
function Info({ title, value, icon, href }: { title: string; value: string; icon?: ReactNode; href?: string }) { return <div className="rounded-lg border p-3"><p className="flex items-center gap-2 text-xs text-muted-foreground">{icon}{title}</p>{href ? <Link to={href} className="mt-1 block break-words text-sm font-medium text-primary underline-offset-4 hover:underline">{value}</Link> : <p className="mt-1 break-words text-sm font-medium">{value}</p>}</div> }
