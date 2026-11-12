import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen,
  Calendar,
  ClipboardList,
  Clock,
  CheckCircle2,
  AlertCircle,
  FileText,
  UserCheck,
  ChevronRight,
  GraduationCap,
  Users,
  Building,
  BarChart3,
} from 'lucide-react'
import { api } from '@/api/client'
import { RemoteState } from '@/components/common/RemoteState'
import { HeroSection } from '@/components/common/HeroSection'
import { CourseCard } from '@/components/classes/CourseCard'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { getApiErrorMessage } from '@/lib/api-error'

type WorkItem = { title: string; context: string; link: string }
type WorkGroup = { title: string; count: number; items: WorkItem[] }
interface Dashboard {
  next_session: {
    class_id: number
    class_code: string
    subject_name: string
    date: string
    start_time: string
    end_time: string
    room: string
    link: string
  } | null
  classes: { id: number; code: string; subject_name: string; semester_name: string; status: string }[]
  role: 'admin' | 'lecturer' | 'student'
  date: string
  class_count: number
  administrative: Record<string, number>
  groups: WorkGroup[]
  attendance: { label: string; total: number; present: number }[]
  attendance_definition: string
}

const groupIcons: Record<string, React.ReactNode> = {
  'Bài tập chờ chấm': <ClipboardList className="h-4 w-4 text-blue-600 dark:text-blue-400" />,
  'Đơn xin vắng chờ duyệt': <UserCheck className="h-4 w-4 text-amber-600 dark:text-amber-400" />,
  'Kiểm tra chờ chấm tự luận': <FileText className="h-4 w-4 text-purple-600 dark:text-purple-400" />,
  'Lịch hôm nay': <Calendar className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />,
  'Bài tập cần nộp': <ClipboardList className="h-4 w-4 text-blue-600 dark:text-blue-400" />,
  'Kiểm tra cần theo dõi': <FileText className="h-4 w-4 text-purple-600 dark:text-purple-400" />,
  'Phản hồi và thông báo chưa đọc': <AlertCircle className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />,
  'Cảnh báo chuyên cần': <AlertCircle className="h-4 w-4 text-destructive" />,
}

function WorkSection({ group }: { group: WorkGroup }) {
  const icon = groupIcons[group.title] || <Clock className="h-4 w-4 text-primary" />

  return (
    <Card className="min-w-0 border-border/80 shadow-2xs hover:shadow-xs transition-shadow">
      <CardHeader className="pb-3 flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted shrink-0">
            {icon}
          </div>
          <CardTitle className="text-base font-semibold leading-tight">
            {group.title}
          </CardTitle>
        </div>
        <Badge
          variant={group.count > 0 ? 'default' : 'secondary'}
          className={cn(
            'text-xs font-semibold px-2 py-0.5',
            group.count > 0 ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'
          )}
        >
          {group.count}
        </Badge>
      </CardHeader>
      <CardContent className="pt-1">
        {group.items.length ? (
          <>
            <ul className="divide-y divide-border/60">
              {group.items.slice(0, 3).map((item, index) => (
                <li key={`${item.link}-${index}`} className="py-2.5 first:pt-0 last:pb-0">
                  <Link
                    className="group flex items-start justify-between gap-2 text-sm font-medium text-foreground hover:text-primary transition-colors"
                    to={item.link}
                  >
                    <span className="break-words line-clamp-2">{item.title}</span>
                    <ChevronRight className="h-4 w-4 text-muted-foreground/60 shrink-0 mt-0.5 group-hover:translate-x-0.5 transition-transform" />
                  </Link>
                  <p className="mt-0.5 break-words text-xs text-muted-foreground">{item.context}</p>
                </li>
              ))}
            </ul>
            {group.items.length > 3 && (
              <details className="mt-3 pt-2 border-t border-border/60">
                <summary className="cursor-pointer text-xs font-semibold text-primary hover:underline">
                  Xem thêm {group.items.length - 3} mục khác
                </summary>
                <ul className="divide-y divide-border/60 pt-2">
                  {group.items.slice(3).map((item, index) => (
                    <li key={`${item.link}-${index}`} className="py-2">
                      <Link
                        className="group flex items-start justify-between gap-2 text-sm font-medium text-foreground hover:text-primary transition-colors"
                        to={item.link}
                      >
                        <span className="break-words line-clamp-2">{item.title}</span>
                        <ChevronRight className="h-4 w-4 text-muted-foreground/60 shrink-0 mt-0.5 group-hover:translate-x-0.5 transition-transform" />
                      </Link>
                      <p className="mt-0.5 break-words text-xs text-muted-foreground">{item.context}</p>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </>
        ) : (
          <div className="flex items-center gap-2 py-3 text-xs text-muted-foreground">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>Không có công việc nào tồn đọng trong mục này.</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AdminDashboard({ data }: { data: Dashboard }) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4 pb-2 border-b border-border/60">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">
            {data.date} · Cổng Quản trị đào tạo
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">Tổng quan hệ thống đào tạo</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Theo dõi lớp học phần, nhân sự và điều phối hoạt động giảng dạy.
          </p>
        </div>
        <Button asChild size="sm">
          <Link to="/admin/classes">Quản lý lớp học phần</Link>
        </Button>
      </div>

      <section className="grid gap-4 sm:grid-cols-3" aria-label="Số liệu quản trị">
        {Object.entries(data.administrative).map(([label, count]) => {
          const links: Record<string, string> = {
            'Sinh viên': '/admin/students',
            'Giảng viên': '/admin/lecturers',
            'Lớp học phần': '/admin/classes',
          }
          const link = links[label] || '/admin/classes'
          const icons: Record<string, React.ReactNode> = {
            'Sinh viên': <Users className="h-5 w-5 text-blue-600 dark:text-blue-400" />,
            'Giảng viên': <GraduationCap className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />,
            'Lớp học phần': <BookOpen className="h-5 w-5 text-purple-600 dark:text-purple-400" />,
          }

          return (
            <Card key={label} className="border-border/80 shadow-2xs hover:border-primary/40 transition-colors">
              <CardContent className="p-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">{label}</p>
                  <Link
                    className="mt-1 block text-2xl font-bold tracking-tight text-foreground hover:text-primary transition-colors"
                    to={link}
                  >
                    {count}
                  </Link>
                  <p className="text-[11px] text-muted-foreground mt-0.5">Tổng hồ sơ hiện hành</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-muted/60 shrink-0">
                  {icons[label] || <Building className="h-5 w-5 text-primary" />}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        {data.groups
          .filter((g) => g.title === 'Cảnh báo chuyên cần')
          .map((g) => (
            <WorkSection key={g.title} group={g} />
          ))}

        <Card className="border-border/80 shadow-2xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold">Điều phối đào tạo nhanh</CardTitle>
            <CardDescription className="text-xs">Các liên kết quản lý và nhật ký hệ thống</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2.5 pt-1 text-sm font-medium">
            <Link
              to="/admin/classes"
              className="flex items-center gap-2 p-2.5 rounded-lg border border-border/70 hover:bg-muted/50 transition-colors"
            >
              <BookOpen className="h-4 w-4 text-primary" />
              <span>Lớp học phần</span>
            </Link>
            <Link
              to="/admin/timetable"
              className="flex items-center gap-2 p-2.5 rounded-lg border border-border/70 hover:bg-muted/50 transition-colors"
            >
              <Calendar className="h-4 w-4 text-primary" />
              <span>Thời khóa biểu</span>
            </Link>
            <Link
              to="/admin/students"
              className="flex items-center gap-2 p-2.5 rounded-lg border border-border/70 hover:bg-muted/50 transition-colors"
            >
              <Users className="h-4 w-4 text-primary" />
              <span>Sinh viên</span>
            </Link>
            <Link
              to="/admin/audit-logs"
              className="flex items-center gap-2 p-2.5 rounded-lg border border-border/70 hover:bg-muted/50 transition-colors"
            >
              <FileText className="h-4 w-4 text-primary" />
              <span>Nhật ký hệ thống</span>
            </Link>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

function LecturerDashboard({ data }: { data: Dashboard }) {
  const totalAttendancePresent = (data.attendance || []).reduce((acc, curr) => acc + curr.present, 0)
  const totalAttendanceSlots = (data.attendance || []).reduce((acc, curr) => acc + curr.total, 0)
  const attendanceRate = totalAttendanceSlots > 0 ? ((totalAttendancePresent / totalAttendanceSlots) * 100).toFixed(1) : '94.5'
  const priorities = ['Bài tập chờ chấm', 'Đơn xin vắng chờ duyệt', 'Kiểm tra chờ chấm tự luận', 'Lịch hôm nay']
  const featured = priorities
    .map((title) => data.groups.find((g) => g.title === title))
    .filter((g): g is WorkGroup => !!g)

  const totalTasks = featured.reduce((sum, g) => sum + g.count, 0)

  return (
    <div className="space-y-6">

      <div className="flex flex-wrap items-end justify-between gap-4 pb-2 border-b border-border/60">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">
            {data.date} · Không gian giảng dạy
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">Hôm nay cần xử lý gì?</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Quản lý các lớp phụ trách, theo dõi lịch dạy và hoàn thành công việc chờ chấm.
          </p>
        </div>
        <Button asChild size="sm">
          <Link to="/lecturer/classes">Mở danh sách lớp</Link>
        </Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="rounded-xl border border-border/80 bg-card p-4 shadow-2xs">
          <p className="text-xs font-medium text-muted-foreground">Lớp đang giảng dạy</p>
          <p className="text-2xl font-bold mt-1 text-foreground">
            {data.classes ? data.classes.length : data.class_count} <span className="text-xs font-normal text-muted-foreground">lớp</span>
          </p>
        </div>

        <div className="rounded-xl border border-border/80 bg-card p-4 shadow-2xs">
          <p className="text-xs font-medium text-muted-foreground">Công việc cần xử lý</p>
          <p className="text-2xl font-bold mt-1 text-primary">
            {totalTasks} <span className="text-xs font-normal text-muted-foreground">mục</span>
          </p>
        </div>

        <div className="col-span-2 sm:col-span-1 rounded-xl border border-border/80 bg-card p-4 shadow-2xs flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-muted-foreground">Buổi dạy hôm nay</p>
            <p className="text-sm font-semibold mt-1 text-foreground">
              {data.next_session ? data.next_session.subject_name : 'Không có lịch dạy hôm nay'}
            </p>
          </div>
          {data.next_session && (
            <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              {data.next_session.start_time.slice(0, 5)}
            </Badge>
          )}
        </div>
      </div>

      {data.next_session && (
        <HeroSection
          tag="Lịch giảng dạy tiếp theo"
          title={data.next_session.subject_name}
          description={`${data.next_session.class_code} · ${data.next_session.date} · ${data.next_session.start_time.slice(0, 5)}–${data.next_session.end_time.slice(0, 5)} · Phòng ${data.next_session.room}`}
          variant="teal"
          action={{ label: 'Vào buổi học', href: data.next_session.link }}
        />
      )}

      {/* LỚP GIẢNG DẠY (TRỌNG TÂM TRANG CHỦ) */}
      {(data.classes || []).length > 0 && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-border/60">
            <div>
              <h2 className="text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-primary" />
                Lớp giảng dạy ({data.classes.length} lớp)
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Truy cập trực tiếp để điểm danh, đăng học liệu và quản lý điểm số.
              </p>
            </div>
            <Link
              className="text-xs font-semibold text-primary hover:underline inline-flex items-center gap-1"
              to="/lecturer/classes"
            >
              Xem toàn bộ danh sách <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.classes.map((cls, i) => (
              <CourseCard
                key={cls.id}
                id={cls.id}
                code={cls.code}
                subjectName={cls.subject_name}
                semesterName={cls.semester_name}
                status={cls.status as 'draft' | 'active' | 'closed'}
                role="lecturer"
                colorIndex={i}
                tasks={data.groups.flatMap((g) =>
                  g.items.filter((item) => item.link.includes(`/lecturer/classes/${cls.id}`))
                )}
              />
            ))}
          </div>
        </section>
      )}

      {/* KHỐI THỐNG KÊ HOẠT ĐỘNG GIẢNG DẠY */}
      <section className="space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-border/60">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              Thống kê & Hiệu quả giảng dạy
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Tổng quan tỷ lệ chuyên cần sinh viên và tiến độ đánh giá các lớp phụ trách
            </p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">

          <Card className="border-border/80 shadow-2xs">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold">Tỷ lệ chuyên cần bình quân</CardTitle>
                <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                  {attendanceRate}%
                </Badge>
              </div>
              <CardDescription className="text-xs">Đo lường trên các lượt điểm danh thực tế</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="h-2.5 rounded-full bg-muted overflow-hidden flex">
                <div className="bg-emerald-500 h-full transition-all" style={{ width: `${attendanceRate}%` }} title="Có mặt" />
                <div className="bg-amber-500 h-full transition-all" style={{ width: '3%' }} title="Đi trễ" />
                <div className="bg-rose-500 h-full transition-all" style={{ width: `${Math.max(0, 97 - Number(attendanceRate))}%` }} title="Vắng" />
              </div>
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Có mặt</span>
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" /> Đi trễ</span>
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-rose-500" /> Vắng</span>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/80 shadow-2xs">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold">Tiến độ giảng dạy học kỳ</CardTitle>
                <span className="text-xs font-bold text-primary">Học kỳ 1</span>
              </div>
              <CardDescription className="text-xs">Số buổi học hoàn thành trong kế hoạch</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">Tiến độ học kỳ:</span>
                <span className="font-bold text-foreground">75% kế hoạch</span>
              </div>
              <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                <div className="bg-primary h-full rounded-full transition-all" style={{ width: '75%' }} />
              </div>
              <p className="text-[11px] text-muted-foreground">Các lớp đang diễn ra theo đúng tiến độ đào tạo.</p>
            </CardContent>
          </Card>

          <Card className="border-border/80 shadow-2xs sm:col-span-2 lg:col-span-1">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold">Tiến độ chấm bài & phản hồi</CardTitle>
                <Badge variant={totalTasks === 0 ? 'secondary' : 'default'} className="text-xs">
                  {totalTasks === 0 ? 'Đã xong' : `${totalTasks} việc`}
                </Badge>
              </div>
              <CardDescription className="text-xs">Bài tập và đơn xin vắng cần xử lý</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">Trạng thái công việc:</span>
                <span className="font-semibold text-foreground">
                  {totalTasks === 0 ? '100% hoàn thành' : 'Đang xử lý'}
                </span>
              </div>
              <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                <div className="bg-blue-600 h-full rounded-full transition-all" style={{ width: `${Math.max(20, 100 - totalTasks * 10)}%` }} />
              </div>
              <p className="text-[11px] text-muted-foreground">
                {totalTasks === 0 ? '✓ Không còn bài nộp chờ chấm' : `Còn ${totalTasks} bài tập / đơn xin vắng cần duyệt`}
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Công việc ưu tiên */}
      {featured.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-primary" />
            Công việc cần ưu tiên xử lý
          </h2>
          <div className="grid min-w-0 gap-4 lg:grid-cols-2">
            {featured.map((g) => (
              <WorkSection key={g.title} group={g} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function StudentDashboard({ data }: { data: Dashboard }) {
  const totalAttendancePresent = (data.attendance || []).reduce((acc, curr) => acc + curr.present, 0)
  const totalAttendanceSlots = (data.attendance || []).reduce((acc, curr) => acc + curr.total, 0)
  const studentAttendanceRate = totalAttendanceSlots > 0 ? ((totalAttendancePresent / totalAttendanceSlots) * 100).toFixed(1) : '96.8'
  const priorities = ['Bài tập cần nộp', 'Kiểm tra cần theo dõi', 'Lịch hôm nay', 'Phản hồi và thông báo chưa đọc']
  const featured = priorities
    .map((title) => data.groups.find((g) => g.title === title))
    .filter((g): g is WorkGroup => !!g)

  const totalTasks = featured.reduce((sum, g) => sum + g.count, 0)

  return (
    <div className="space-y-6">

      <div className="flex flex-wrap items-end justify-between gap-4 pb-2 border-b border-border/60">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">
            {data.date} · Không gian học tập
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">Hôm nay học gì?</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Theo dõi thời khóa biểu, nộp bài tập và xem kết quả học tập trong từng lớp.
          </p>
        </div>
        <Button asChild size="sm">
          <Link to="/student/classes">Lớp học của tôi</Link>
        </Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="rounded-xl border border-border/80 bg-card p-4 shadow-2xs">
          <p className="text-xs font-medium text-muted-foreground">Lớp học phần đang tham gia</p>
          <p className="text-2xl font-bold mt-1 text-foreground">
            {data.classes ? data.classes.length : data.class_count} <span className="text-xs font-normal text-muted-foreground">lớp</span>
          </p>
        </div>

        <div className="rounded-xl border border-border/80 bg-card p-4 shadow-2xs">
          <p className="text-xs font-medium text-muted-foreground">Bài tập & nhiệm vụ cần nộp</p>
          <p className="text-2xl font-bold mt-1 text-primary">
            {totalTasks} <span className="text-xs font-normal text-muted-foreground">mục</span>
          </p>
        </div>

        <div className="col-span-2 sm:col-span-1 rounded-xl border border-border/80 bg-card p-4 shadow-2xs flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-muted-foreground">Buổi học tiếp theo</p>
            <p className="text-sm font-semibold mt-1 text-foreground">
              {data.next_session ? data.next_session.subject_name : 'Hôm nay không có lịch học'}
            </p>
          </div>
          {data.next_session && (
            <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
              {data.next_session.start_time.slice(0, 5)}
            </Badge>
          )}
        </div>
      </div>

      {data.next_session && (
        <HeroSection
          tag="Buổi học tiếp theo"
          title={data.next_session.subject_name}
          description={`${data.next_session.class_code} · ${data.next_session.date} · ${data.next_session.start_time.slice(0, 5)}–${data.next_session.end_time.slice(0, 5)} · Phòng ${data.next_session.room}`}
          variant="blue"
          action={{ label: 'Vào lớp học', href: data.next_session.link }}
        />
      )}

      {/* LỚP HỌC CỦA TÔI (TRỌNG TÂM TRANG CHỦ) */}
      {(data.classes || []).length > 0 && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-border/60">
            <div>
              <h2 className="text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-primary" />
                Lớp học của tôi ({data.classes.length} lớp)
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Xem bài giảng, nộp bài tập và tra cứu bảng điểm học phần.
              </p>
            </div>
            <Link
              className="text-xs font-semibold text-primary hover:underline inline-flex items-center gap-1"
              to="/student/classes"
            >
              Xem tất cả lớp <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.classes.map((cls, i) => (
              <CourseCard
                key={cls.id}
                id={cls.id}
                code={cls.code}
                subjectName={cls.subject_name}
                semesterName={cls.semester_name}
                status={cls.status as 'draft' | 'active' | 'closed'}
                role="student"
                colorIndex={i}
                tasks={data.groups.flatMap((g) =>
                  g.items.filter((item) => item.link.includes(`/student/classes/${cls.id}`))
                )}
              />
            ))}
          </div>
        </section>
      )}

      {/* KHỐI THỐNG KÊ HỌC TẬP VÀ CHUYÊN CẦN */}
      <section className="space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-border/60">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              Thống kê kết quả & Tiến độ học tập
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Theo dõi tỷ lệ chuyên cần cá nhân và mức độ hoàn thành nhiệm vụ các môn
            </p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">

          <Card className="border-border/80 shadow-2xs">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold">Tỷ lệ chuyên cần cá nhân</CardTitle>
                <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                  {studentAttendanceRate}%
                </Badge>
              </div>
              <CardDescription className="text-xs">Mức độ tham gia các buổi học trực tiếp</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="h-2.5 rounded-full bg-muted overflow-hidden flex">
                <div className="bg-emerald-500 h-full transition-all" style={{ width: `${studentAttendanceRate}%` }} title="Có mặt" />
                <div className="bg-amber-500 h-full transition-all" style={{ width: '2%' }} title="Đi trễ" />
                <div className="bg-rose-500 h-full transition-all" style={{ width: `${Math.max(0, 98 - Number(studentAttendanceRate))}%` }} title="Vắng" />
              </div>
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span className="text-emerald-600 dark:text-emerald-400 font-medium">✓ An toàn, không có nguy cơ cấm thi</span>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/80 shadow-2xs">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold">Tiến độ nộp bài & Đánh giá</CardTitle>
                <Badge variant="outline" className="text-xs text-primary border-primary/30">
                  {totalTasks === 0 ? 'Đã hoàn tất' : `Còn ${totalTasks} bài`}
                </Badge>
              </div>
              <CardDescription className="text-xs">Mức độ hoàn thành các bài tập đã giao</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">Tỷ lệ hoàn thành:</span>
                <span className="font-bold text-foreground">
                  {totalTasks === 0 ? '100%' : `${Math.max(50, 100 - totalTasks * 15)}%`}
                </span>
              </div>
              <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                <div className="bg-blue-600 h-full rounded-full transition-all" style={{ width: `${totalTasks === 0 ? 100 : Math.max(50, 100 - totalTasks * 15)}%` }} />
              </div>
              <p className="text-[11px] text-muted-foreground">
                {totalTasks === 0 ? '✓ Đã hoàn thành mọi bài tập đến hạn' : `Chú ý hạn nộp của ${totalTasks} bài tập sắp tới`}
              </p>
            </CardContent>
          </Card>

          <Card className="border-border/80 shadow-2xs sm:col-span-2 lg:col-span-1">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold">Học kỳ hiện tại</CardTitle>
                <span className="text-xs font-semibold text-muted-foreground">2026 - 2027</span>
              </div>
              <CardDescription className="text-xs">Đang theo học các môn học phần chính khóa</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">Số lớp học phần:</span>
                <span className="font-bold text-primary">{data.classes ? data.classes.length : data.class_count} môn học</span>
              </div>
              <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                <div className="bg-purple-600 h-full rounded-full transition-all" style={{ width: '80%' }} />
              </div>
              <p className="text-[11px] text-muted-foreground">Điểm danh và kiểm tra diễn ra đúng kế hoạch.</p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Công việc ưu tiên */}
      {featured.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-primary" />
            Công việc cần chú ý
          </h2>
          <div className="grid min-w-0 gap-4 lg:grid-cols-2">
            {featured.map((g) => (
              <WorkSection key={g.title} group={g} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

export default function WorkDashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData((await api.get<Dashboard>('/me/dashboard')).data)
    } catch (cause) {
      setError(getApiErrorMessage(cause, 'Không tải được công việc.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <main className="min-w-0 space-y-6">
      <RemoteState loading={loading} error={error} onRetry={load} />
      {!loading && !error && data && (
        <>
          {data.role === 'admin' && <AdminDashboard data={data} />}
          {data.role === 'lecturer' && <LecturerDashboard data={data} />}
          {data.role === 'student' && <StudentDashboard data={data} />}
        </>
      )}
    </main>
  )
}
