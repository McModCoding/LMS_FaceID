import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { BookOpen, CalendarDays, ClipboardList, Megaphone } from 'lucide-react'
import api from '@/api/client'
import { learningApi, type Announcement } from '@/api/learning'
import { materialsApi, type Material } from '@/api/materials'
import { RemoteState } from '@/components/common/RemoteState'
import { HeroSection } from '@/components/common/HeroSection'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getApiErrorMessage } from '@/lib/api-error'
import type { Class } from '@/types/class'

type WorkItem = { title: string; context: string; class_id: number | null; link: string }
type Dashboard = { groups: { title: string; items: WorkItem[] }[] }

export function ClassOverview({ classData, student = false }: { classData: Class; student?: boolean }) {
  const location = useLocation()
  const [work, setWork] = useState<Dashboard | null>(null)
  const [materials, setMaterials] = useState<Material[] | null>(null)
  const [notices, setNotices] = useState<Announcement[] | null>(null)
  const [errors, setErrors] = useState({ work: '', materials: '', notices: '' })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    setWork(null)
    setMaterials(null)
    setNotices(null)
    setErrors({ work: '', materials: '', notices: '' })

    const fail = (key: 'work' | 'materials' | 'notices', cause: unknown) => {
      if (active) setErrors((prev) => ({ ...prev, [key]: getApiErrorMessage(cause, 'Không tải được nội dung.') }))
    }

    api.get<Dashboard>('/me/dashboard').then((r) => { if (active) setWork(r.data) }).catch((cause) => fail('work', cause))
    materialsApi.list(classData.id, 1).then((r) => { if (active) setMaterials(r.items) }).catch((cause) => fail('materials', cause))
    learningApi.announcements(classData.id).then((r) => { if (active) setNotices(r) }).catch((cause) => fail('notices', cause))

    return () => { active = false }
  }, [classData.id, reload])

  const route = (tab: string) => `${location.pathname}?tab=${tab}`
  const relevant = student
    ? ['Kiểm tra cần theo dõi', 'Bài tập cần nộp', 'Cảnh báo chuyên cần']
    : ['Bài tập chờ chấm', 'Đơn xin vắng chờ duyệt', 'Kiểm tra chờ chấm tự luận', 'Cảnh báo chuyên cần']

  const taskGroups = relevant.map(
    (title) => (work?.groups.find((group) => group.title === title)?.items || []).filter((item) => item.class_id === classData.id)
  )
  const tasks = [0, 1, 2].flatMap((index) => taskGroups.flatMap((group) => (group[index] ? [group[index]] : []))).slice(0, 3)
  const retry = () => setReload((n) => n + 1)

  const statusLabel = classData.status === 'closed' ? 'Đã kết thúc' : classData.status === 'draft' ? 'Bản nháp' : 'Đang hoạt động'

  return (
    <div className="space-y-4">
      <HeroSection
        tag={`${classData.code} · ${statusLabel}`}
        title={classData.subject_name || classData.code}
        description={`Giảng viên: ${classData.lecturer_name || 'Chưa phân công'} · ${classData.semester_name || 'Học kỳ hiện tại'}`}
        variant={classData.status === 'closed' ? 'warm' : 'blue'}
        action={{ label: 'Xem lịch lớp', href: route('schedules') }}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Việc cần làm */}
        <Card className="min-w-0">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <ClipboardList className="h-4 w-4 text-primary" />
              {student ? 'Việc học tiếp theo' : 'Công việc cần xử lý'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <RemoteState loading={!work && !errors.work} error={errors.work} onRetry={retry} />
            {work &&
              (tasks.length ? (
                <ul className="space-y-3">
                  {tasks.map((item, index) => (
                    <li key={`${item.link}-${index}`} className="border-b pb-3 last:border-0 last:pb-0">
                      <Link className="break-words font-medium text-primary hover:underline" to={item.link}>
                        {item.title}
                      </Link>
                      <p className="mt-0.5 text-xs text-muted-foreground">{item.context}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Chưa có công việc trong các nhóm hiển thị. Mở từng mục để xem chi tiết.</p>
              ))}
          </CardContent>
        </Card>

        {/* Thông tin lớp */}
        <Card className="min-w-0">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarDays className="h-4 w-4 text-primary" />
              Thông tin lớp
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p>
              <span className="text-muted-foreground">Mã môn:</span> {classData.subject_code || 'Chưa cập nhật'}
            </p>
            <p>
              <span className="text-muted-foreground">Giảng viên:</span> {classData.lecturer_name || 'Chưa phân công'}
            </p>
            <Link className="inline-block font-medium text-primary hover:underline" to={route('schedules')}>
              Xem lịch và buổi học →
            </Link>
            <details className="rounded-lg border bg-muted/40 p-3 pt-2">
              <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">Quy định chuyên cần</summary>
              <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
                Đi trễ sau {classData.late_after_min} phút · Tính vắng sau {classData.absent_after_min} phút · Cảnh báo từ {classData.attendance_warning_absences} buổi vắng.
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Trọng số: có mặt {classData.weight_present} · trễ {classData.weight_late} · có phép {classData.weight_excused}.
              </p>
            </details>
          </CardContent>
        </Card>

        {/* Học liệu gần đây */}
        <Card className="min-w-0">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <BookOpen className="h-4 w-4 text-primary" />
              Học liệu gần đây
            </CardTitle>
          </CardHeader>
          <CardContent>
            <RemoteState loading={!materials && !errors.materials} error={errors.materials} onRetry={retry} />
            {materials &&
              (materials.length ? (
                <ul className="space-y-3">
                  {materials.slice(0, 3).map((item) => (
                    <li key={item.id} className="break-words border-b pb-2.5 last:border-0 last:pb-0">
                      <Link className="font-medium text-primary hover:underline text-sm" to={route('materials')}>
                        {item.title}
                      </Link>
                      <p className="text-xs text-muted-foreground mt-0.5">{item.url ? '↗ Liên kết trực tuyến' : '▥ Tài liệu tệp tải về'}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Lớp chưa có học liệu.</p>
              ))}
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Megaphone className="h-4 w-4 text-primary" />
              Thông báo mới
            </CardTitle>
          </CardHeader>
          <CardContent>
            <RemoteState loading={!notices && !errors.notices} error={errors.notices} onRetry={retry} />
            {notices &&
              (notices.length ? (
                <ul className="space-y-3">
                  {notices.slice(0, 3).map((item) => (
                    <li key={item.id} className="break-words border-b pb-2.5 last:border-0 last:pb-0">
                      <Link className="font-medium text-primary hover:underline text-sm" to={route('announcements')}>
                        {item.title}
                      </Link>
                      <p className="text-xs text-muted-foreground mt-0.5">{item.author_name}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">Chưa có thông báo trong lớp.</p>
              ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
