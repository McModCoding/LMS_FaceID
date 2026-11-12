import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Building2,
  Mail,
  Phone,
  GraduationCap,
  KeyRound,
  BookOpen,
  Award,
  ChevronRight,
  ShieldCheck,
  Calendar,
} from 'lucide-react'
import { toast } from 'sonner'
import { lecturersApi } from '../../api/lecturers'
import { classesApi } from '../../api/classes'
import { Lecturer } from '../../types/lecturer'
import { Class } from '../../types/class'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

export default function LecturerProfilePage() {
  const [profile, setProfile] = useState<Lecturer | null>(null)
  const [classes, setClasses] = useState<Class[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    void Promise.all([lecturersApi.getMe(), classesApi.getAll({ page: 1, page_size: 100 })])
      .then(([lecturer, classResult]) => {
        setProfile(lecturer)
        setClasses(classResult.items)
      })
      .catch((error) => {
        toast.error(error?.response?.data?.detail?.message || 'Không thể tải hồ sơ cá nhân')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  if (loading || !profile) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-44 w-full rounded-2xl" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  const initials = profile.full_name
    ? profile.full_name
        .split(' ')
        .map((n) => n[0])
        .slice(-2)
        .join('')
        .toUpperCase()
    : 'GV'

  return (
    <div className="space-y-6">

      <div className="relative overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 text-white p-6 sm:p-8 shadow-sm">
        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="flex items-center gap-4 sm:gap-6">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-white/10 backdrop-blur border border-white/20 text-2xl font-bold shadow-md">
              {initials}
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">{profile.full_name}</h1>
                <Badge className="bg-emerald-500/90 hover:bg-emerald-500 text-white border-0 text-xs font-semibold">
                  {profile.type === 'full_time' ? 'Giảng viên Cơ hữu' : 'Giảng viên Thỉnh giảng'}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-slate-300 font-mono">
                Mã giảng viên: <span className="font-semibold text-white">{profile.code}</span> · {profile.department_name || profile.department || 'Khoa Công nghệ thông tin'}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-300">
                <span className="flex items-center gap-1">
                  <Award className="h-3.5 w-3.5 text-blue-400" />
                  {profile.degree || 'Tiến sĩ'}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                  Tài khoản đã xác thực
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap sm:flex-col gap-2 self-start sm:self-center">
            <Button
              variant="secondary"
              size="sm"
              className="gap-1.5 bg-white/15 hover:bg-white/25 text-white border-white/20 text-xs"
              onClick={() => navigate('/change-password')}
            >
              <KeyRound className="h-3.5 w-3.5" />
              Đổi mật khẩu
            </Button>
            <Button
              asChild
              variant="secondary"
              size="sm"
              className="gap-1.5 bg-white/15 hover:bg-white/25 text-white border-white/20 text-xs"
            >
              <Link to="/lecturer/classes">
                <BookOpen className="h-3.5 w-3.5" />
                Lớp giảng dạy
              </Link>
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {/* Card 1: Chuyên môn & Đào tạo */}
        <Card className="border-border/80 shadow-2xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <GraduationCap className="h-4 w-4 text-primary" />
              Thông tin học vụ & Chuyên môn
            </CardTitle>
            <CardDescription className="text-xs">Đơn vị quản trị và học vị công tác</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <Building2 className="h-3.5 w-3.5 text-primary" /> Khoa phụ trách:
              </span>
              <span className="font-semibold text-foreground text-right">
                {profile.department_name || profile.department || 'Công nghệ thông tin'}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <Award className="h-3.5 w-3.5 text-primary" /> Học vị / Học hàm:
              </span>
              <span className="font-semibold text-foreground">{profile.degree || 'Tiến sĩ'}</span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" /> Loại hình công tác:
              </span>
              <Badge variant="outline" className="text-xs">
                {profile.type === 'full_time' ? 'Cơ hữu chính thức' : 'Thỉnh giảng'}
              </Badge>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <Calendar className="h-3.5 w-3.5 text-primary" /> Tổng số lớp phụ trách:
              </span>
              <span className="font-bold text-primary">{classes.length} lớp học phần</span>
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Liên hệ & Tài khoản */}
        <Card className="border-border/80 shadow-2xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Mail className="h-4 w-4 text-primary" />
              Thông tin liên hệ & Bảo mật
            </CardTitle>
            <CardDescription className="text-xs">Kênh liên lạc công vụ và trạng thái tài khoản</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <Mail className="h-3.5 w-3.5 text-primary" /> Email công vụ:
              </span>
              <span className="font-medium text-foreground">{profile.email || 'gv001@lms.local'}</span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <Phone className="h-3.5 w-3.5 text-primary" /> Số điện thoại:
              </span>
              <span className="font-medium text-foreground">{profile.phone || '0900000001'}</span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <KeyRound className="h-3.5 w-3.5 text-primary" /> Tên đăng nhập:
              </span>
              <span className="font-mono text-xs font-semibold text-foreground">{profile.code}</span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" /> Trạng thái hồ sơ:
              </span>
              <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                Đang hoạt động
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 3. Lớp đang phụ trách */}
      <Card className="border-border/80 shadow-2xs">
        <CardHeader className="pb-3 flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-primary" />
              Lớp học phần đang phụ trách ({classes.length} lớp)
            </CardTitle>
            <CardDescription className="text-xs">
              Các lớp học phần được phân công trong các học kỳ hiện tại và gần nhất
            </CardDescription>
          </div>
          <Button asChild variant="outline" size="sm" className="text-xs">
            <Link to="/lecturer/classes">Xem tất cả</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {classes.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              Bạn chưa được phân công lớp học phần nào trong học kỳ này.
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {classes.map((cls) => (
                <div
                  key={cls.id}
                  className="group rounded-xl border border-border/80 bg-card p-4 hover:border-primary/40 hover:shadow-xs transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-bold text-primary">{cls.code}</span>
                      <Badge variant="outline" className="text-[10px]">
                        {cls.status === 'active' ? 'Đang mở' : cls.status === 'closed' ? 'Đã đóng' : 'Bản nháp'}
                      </Badge>
                    </div>
                    <h3 className="font-semibold text-sm text-foreground mt-2 line-clamp-1 group-hover:text-primary transition-colors">
                      {cls.subject_name || cls.code}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">{cls.semester_name || 'Học kỳ 1'}</p>
                  </div>

                  <div className="pt-3 mt-3 border-t border-border/60 flex items-center justify-between">
                    <span className="text-[11px] text-muted-foreground">
                      Sĩ số: {cls.enrolled_count ?? 0} sinh viên
                    </span>
                    <Link
                      to={`/lecturer/classes/${cls.id}`}
                      className="text-xs font-semibold text-primary hover:underline inline-flex items-center gap-0.5"
                    >
                      Chi tiết <ChevronRight className="h-3 w-3" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
