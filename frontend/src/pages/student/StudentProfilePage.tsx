import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Building2,
  Mail,
  Phone,
  GraduationCap,
  KeyRound,
  BookOpen,
  ScanFace,
  ChevronRight,
  ShieldCheck,
  Calendar,
  UserCheck,
} from 'lucide-react'
import { toast } from 'sonner'
import { studentsApi } from '../../api/students'
import { classesApi } from '../../api/classes'
import { Student } from '../../types/student'
import { Class } from '../../types/class'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

export default function StudentProfilePage() {
  const [profile, setProfile] = useState<Student | null>(null)
  const [classes, setClasses] = useState<Class[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    void Promise.all([studentsApi.getMe(), classesApi.getAll({ page: 1, page_size: 100 })])
      .then(([student, classResult]) => {
        setProfile(student)
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
    : 'SV'

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
                <Badge className="bg-blue-500/90 hover:bg-blue-500 text-white border-0 text-xs font-semibold">
                  Sinh viên chính quy
                </Badge>
              </div>
              <p className="mt-1 text-sm text-slate-300 font-mono">
                MSSV: <span className="font-semibold text-white">{profile.student_code}</span> · {profile.department_name || 'Khoa Công nghệ thông tin'}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-300">
                <span className="flex items-center gap-1">
                  <UserCheck className="h-3.5 w-3.5 text-blue-400" />
                  Lớp: {profile.admin_class || 'CNTT K21'}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                  Trạng thái: {profile.status === 'studying' ? 'Đang học' : 'Bảo lưu'}
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
              variant="secondary"
              size="sm"
              className="gap-1.5 bg-white/15 hover:bg-white/25 text-white border-white/20 text-xs"
              onClick={() => navigate('/student/face')}
            >
              <ScanFace className="h-3.5 w-3.5" />
              Đăng ký FaceID
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {/* Card 1: Học vụ & Sinh viên */}
        <Card className="border-border/80 shadow-2xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <GraduationCap className="h-4 w-4 text-primary" />
              Thông tin học vụ & Sinh viên
            </CardTitle>
            <CardDescription className="text-xs">Đơn vị quản lý và tình trạng đào tạo</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <Building2 className="h-3.5 w-3.5 text-primary" /> Khoa trực thuộc:
              </span>
              <span className="font-semibold text-foreground text-right">
                {profile.department_name || 'Công nghệ thông tin'}
              </span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <UserCheck className="h-3.5 w-3.5 text-primary" /> Lớp hành chính:
              </span>
              <span className="font-semibold text-foreground">{profile.admin_class || 'Chưa cập nhật'}</span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" /> Trạng thái sinh viên:
              </span>
              <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                {profile.status === 'studying' ? 'Đang học' : profile.status === 'suspended' ? 'Bảo lưu' : 'Đã tốt nghiệp'}
              </Badge>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <Calendar className="h-3.5 w-3.5 text-primary" /> Ngày sinh:
              </span>
              <span className="font-medium text-foreground">{profile.dob || 'Chưa cập nhật'}</span>
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
            <CardDescription className="text-xs">Kênh liên lạc học vụ và bảo mật sinh viên</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <Mail className="h-3.5 w-3.5 text-primary" /> Email sinh viên:
              </span>
              <span className="font-medium text-foreground">{profile.email || `${profile.student_code.toLowerCase()}@lms.local`}</span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <Phone className="h-3.5 w-3.5 text-primary" /> Số điện thoại:
              </span>
              <span className="font-medium text-foreground">{profile.phone || '0900000000'}</span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-border/60">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <KeyRound className="h-3.5 w-3.5 text-primary" /> Tên đăng nhập:
              </span>
              <span className="font-mono text-xs font-semibold text-foreground">{profile.student_code}</span>
            </div>

            <div className="flex items-center justify-between py-2">
              <span className="text-muted-foreground flex items-center gap-2 text-xs">
                <ScanFace className="h-3.5 w-3.5 text-primary" /> Khuôn mặt FaceID:
              </span>
              <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                Đã đăng ký nhận diện
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 3. Lớp học phần đang tham gia */}
      <Card className="border-border/80 shadow-2xs">
        <CardHeader className="pb-3 flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-primary" />
              Lớp học phần của tôi ({classes.length} lớp)
            </CardTitle>
            <CardDescription className="text-xs">
              Các lớp học phần bạn đang tham gia học tập trong học kỳ này
            </CardDescription>
          </div>
          <Button asChild variant="outline" size="sm" className="text-xs">
            <Link to="/student/classes">Xem tất cả</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {classes.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              Bạn chưa được ghi danh vào lớp học phần nào.
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
                        {cls.status === 'active' ? 'Đang học' : cls.status === 'closed' ? 'Đã kết thúc' : 'Bản nháp'}
                      </Badge>
                    </div>
                    <h3 className="font-semibold text-sm text-foreground mt-2 line-clamp-1 group-hover:text-primary transition-colors">
                      {cls.subject_name || cls.code}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">{cls.semester_name || 'Học kỳ 1'}</p>
                  </div>

                  <div className="pt-3 mt-3 border-t border-border/60 flex items-center justify-between">
                    <span className="text-[11px] text-muted-foreground">
                      {cls.subject_code || 'Chính khóa'}
                    </span>
                    <Link
                      to={`/student/classes/${cls.id}`}
                      className="text-xs font-semibold text-primary hover:underline inline-flex items-center gap-0.5"
                    >
                      Vào lớp học <ChevronRight className="h-3 w-3" />
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
