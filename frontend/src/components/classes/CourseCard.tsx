import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import type { ClassStatus } from '@/types/class'

interface CourseTask {
  title: string
  context: string
  link: string
}

interface CourseCardProps {
  id: number
  code: string
  subjectName: string
  teacherName?: string
  schedule?: string
  semesterName: string
  status: ClassStatus
  tasks?: CourseTask[]
  role: 'student' | 'lecturer' | 'admin'
  colorIndex?: number // 0, 1, 2 → blue, teal, violet
}

const bannerColors = ['course-banner-blue', 'course-banner-teal', 'course-banner-violet'] as const

const taskLabel: Record<string, string> = {
  student: 'Sắp đến hạn & thông báo',
  lecturer: 'Công việc của lớp',
  admin: 'Thông tin lớp',
}

export function CourseCard({
  id,
  code,
  subjectName,
  teacherName,
  schedule,
  semesterName,
  status,
  tasks = [],
  role,
  colorIndex = 0,
}: CourseCardProps) {
  const banner = bannerColors[colorIndex % 3]
  const closed = status === 'closed'
  const classLink = `/${role === 'admin' ? 'admin' : role}/classes/${id}`

  return (
    <article className="flex flex-col overflow-hidden rounded-xl border bg-card shadow-sm transition-shadow hover:shadow-md">

      <header className={cn('relative isolate flex min-h-[160px] flex-col p-4 overflow-hidden', banner)}>
        <div className="course-banner-decoration" aria-hidden="true" />
        <p className="text-xs font-semibold tracking-wide opacity-90">{code} · HỌC KỲ</p>
        <Link
          to={classLink}
          className="mt-2 line-clamp-2 text-lg font-bold leading-snug hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-white focus-visible:outline-offset-2"
          aria-label={`Vào lớp ${subjectName}`}
        >
          {subjectName}
        </Link>
        {teacherName && (
          <p className="mt-1 text-sm opacity-90 truncate">{teacherName}</p>
        )}
        {schedule && (
          <p className="text-xs opacity-80 truncate">{schedule}</p>
        )}
        <div className="mt-auto pt-2 text-xs font-semibold opacity-90">
          ● {closed ? 'Đã kết thúc' : role === 'lecturer' ? 'Đang dạy' : role === 'student' ? 'Đang học' : 'Đang hoạt động'}
        </div>
      </header>

      <div className="flex flex-1 flex-col p-4">
        <h3 className="mb-2 text-xs font-semibold text-muted-foreground">
          {closed ? 'Lớp đã kết thúc' : taskLabel[role]}
        </h3>
        {closed ? (
          <p className="text-sm text-muted-foreground">Xem lại học liệu và kết quả của lớp.</p>
        ) : tasks.length > 0 ? (
          <ul className="space-y-0 divide-y divide-border">
            {tasks.slice(0, 3).map((task, i) => (
              <li key={i} className="py-2.5">
                <Link
                  to={task.link}
                  className="block text-sm font-semibold text-primary line-clamp-2 hover:underline"
                >
                  {task.title}
                </Link>
                <p className="mt-0.5 text-xs text-muted-foreground line-clamp-1">{task.context}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Chưa có công việc hoặc thông báo mới.</p>
        )}
      </div>

      <footer className="flex items-center justify-between border-t px-4 py-3">
        <span className="text-xs text-muted-foreground">{semesterName}</span>
        <Link
          to={classLink}
          className="inline-flex h-8 items-center rounded-md bg-primary px-3 text-xs font-semibold text-primary-foreground hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
        >
          {closed ? 'Xem lịch sử' : 'Vào lớp'}
        </Link>
      </footer>
    </article>
  )
}
