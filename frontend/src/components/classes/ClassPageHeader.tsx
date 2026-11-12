import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { ClassStatusBadge } from '@/components/common/status-badge'
import type { ClassStatus } from '@/types/class'

interface ClassPageHeaderProps {
  code: string
  subjectName: string
  semesterName?: string | null
  lecturerName?: string | null
  status: ClassStatus
  backHref: string
  backLabel?: string
  studentView?: boolean
  actions?: React.ReactNode
}

export function ClassPageHeader({
  code,
  subjectName,
  semesterName,
  lecturerName,
  status,
  backHref,
  backLabel = 'Danh sách lớp',
  studentView = false,
  actions,
}: ClassPageHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 pb-4">
      <div className="min-w-0 space-y-1">
        <Button asChild variant="ghost" size="sm" className="-ml-2 h-8 text-muted-foreground hover:text-foreground">
          <Link to={backHref}>
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            {backLabel}
          </Link>
        </Button>
        <div className="flex flex-wrap items-center gap-2.5 pt-0.5">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">{subjectName}</h1>
          <ClassStatusBadge status={status} studentView={studentView} />
        </div>
        <p className="text-sm text-muted-foreground">
          {code} {semesterName ? `· ${semesterName}` : ''} {lecturerName ? `· Giảng viên: ${lecturerName}` : ''}
        </p>
      </div>
      {actions && <div className="flex items-center gap-2 pt-1">{actions}</div>}
    </div>
  )
}
