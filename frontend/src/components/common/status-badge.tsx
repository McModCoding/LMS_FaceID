import { CheckCircle2, CircleDashed, Clock3, FileText, PlayCircle, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { AttendanceStatus } from '@/types/attendance'
import type { SessionStatus } from '@/types/session'
import type { ClassStatus } from '@/types/class'

type AttendanceDisplayStatus = AttendanceStatus | 'pending'

const attendanceConfig: Record<AttendanceDisplayStatus, { label: string; variant: 'success' | 'warning' | 'destructive' | 'secondary' | 'outline'; icon: typeof CheckCircle2 }> = {
  present: { label: 'Có mặt', variant: 'success', icon: CheckCircle2 },
  late: { label: 'Đi muộn', variant: 'warning', icon: Clock3 },
  absent: { label: 'Vắng', variant: 'destructive', icon: XCircle },
  excused: { label: 'Có phép', variant: 'secondary', icon: CheckCircle2 },
  pending: { label: 'Chưa điểm danh', variant: 'outline', icon: CircleDashed },
}

export function AttendanceStatusBadge({ status }: { status: AttendanceDisplayStatus }) {
  const config = attendanceConfig[status]
  const Icon = config.icon
  return <Badge variant={config.variant} className="gap-1"><Icon className="h-3 w-3" />{config.label}</Badge>
}

const sessionConfig: Record<SessionStatus, { label: string; variant: 'success' | 'destructive' | 'secondary' | 'outline'; icon: typeof CheckCircle2 }> = {
  scheduled: { label: 'Sắp diễn ra', variant: 'outline', icon: Clock3 },
  open: { label: 'Đang mở', variant: 'success', icon: PlayCircle },
  closed: { label: 'Đã đóng', variant: 'secondary', icon: CheckCircle2 },
  cancelled: { label: 'Đã hủy', variant: 'destructive', icon: XCircle },
}

export function SessionStatusBadge({ status }: { status: SessionStatus }) {
  const config = sessionConfig[status]
  const Icon = config.icon
  return <Badge variant={config.variant} className="gap-1"><Icon className="h-3 w-3" />{config.label}</Badge>
}

const classConfig: Record<ClassStatus, { label: string; variant: 'success' | 'warning' | 'secondary'; icon: typeof CheckCircle2 }> = {
  draft: { label: 'Nháp', variant: 'warning', icon: FileText },
  active: { label: 'Đang hoạt động', variant: 'success', icon: CheckCircle2 },
  closed: { label: 'Đã đóng', variant: 'secondary', icon: CheckCircle2 },
}

export function ClassStatusBadge({ status, studentView = false }: { status: ClassStatus; studentView?: boolean }) {
  const config = classConfig[status]
  const Icon = config.icon
  const label = studentView && status === 'active' ? 'Đang học' : studentView && status === 'closed' ? 'Đã kết thúc' : config.label
  return <Badge variant={config.variant} className="gap-1"><Icon className="h-3 w-3" />{label}</Badge>
}
