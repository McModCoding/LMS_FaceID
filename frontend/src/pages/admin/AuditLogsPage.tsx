import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ScrollText,
  Search,
  Filter,
  RotateCcw,
  Eye,
  Clock,
} from 'lucide-react'
import { auditApi } from '@/api/audit'
import { AuditLog } from '@/types/user'
import { getApiErrorMessage } from '@/lib/api-error'
import { RemoteState, Pagination } from '@/components/common/RemoteState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

type AuditDetail = Record<string, unknown>

const actionLabels: Record<string, string> = {
  SAVE_GRADE_COMPONENT: 'Lưu thành phần điểm',
  DELETE_GRADE_COMPONENT: 'Xóa thành phần điểm',
  UPDATE_MANUAL_GRADE: 'Nhập / sửa điểm tay',
  PUBLISH_GRADEBOOK: 'Công bố bảng điểm',
  EXPORT_GRADEBOOK: 'Xuất bảng điểm',
  GRADE_ASSIGNMENT: 'Chấm bài tập',
  RESET_ASSIGNMENT_GRADE: 'Xóa điểm khi nộp lại',
  UPDATE_ASSIGNMENT_GRADE_SOURCE: 'Đổi cấu hình điểm bài tập',
  PUBLISH_EXAM: 'Công bố bài kiểm tra',
  CLOSE_EXAM: 'Đóng bài kiểm tra',
  UPDATE_EXAM_CLOSE_TIME: 'Đổi giờ đóng bài kiểm tra',
  GRADE_EXAM_ESSAY: 'Chấm tự luận',
  EXPORT_EXAM_RESULTS: 'Xuất kết quả kiểm tra',
  CREATE_EXAM_DRAFT: 'Tạo đề nháp',
  UPDATE_EXAM_DRAFT: 'Sửa đề kiểm tra',
  DELETE_EXAM_DRAFT: 'Xóa đề nháp',
  CREATE_QUESTION: 'Tạo câu hỏi',
  UPDATE_QUESTION: 'Sửa câu hỏi',
  DELETE_QUESTION: 'Xóa câu hỏi',
  LOGIN: 'Đăng nhập',
  CHANGE_PASSWORD: 'Đổi mật khẩu',
  TOGGLE_USER_STATUS: 'Đổi trạng thái tài khoản',
  RESET_PASSWORD: 'Đặt lại mật khẩu',
  IMPORT_STUDENTS: 'Nhập danh sách sinh viên',
  PATCH_ATTENDANCE: 'Cập nhật điểm danh',
  BULK_PATCH_ATTENDANCE: 'Cập nhật điểm danh hàng loạt',
  MARK_REMAINING_ATTENDANCE: 'Đánh dấu điểm danh còn lại',
  CHECK_IN_STUDENT: 'Ghi nhận điểm danh',
  OPEN_SESSION: 'Mở buổi học',
  CLOSE_SESSION: 'Đóng buổi học',
  REOPEN_SESSION: 'Mở lại buổi học',
  AUTO_CLOSE_SESSION: 'Tự động đóng buổi học',
  CREATE_CLASS: 'Tạo lớp học phần',
  UPDATE_CLASS: 'Cập nhật lớp học phần',
  ACTIVATE_CLASS: 'Kích hoạt lớp học phần',
  CLOSE_CLASS: 'Đóng lớp học phần',
  DELETE_CLASS: 'Xóa lớp học phần',
  CREATE_SEMESTER: 'Tạo học kỳ',
  UPDATE_SEMESTER: 'Cập nhật học kỳ',
  DELETE_SEMESTER: 'Xóa học kỳ',
}

const entityLabels: Record<string, string> = {
  grade_components: 'Thành phần điểm',
  assignments: 'Bài tập',
  submissions: 'Bài nộp',
  exams: 'Bài kiểm tra',
  exam_attempts: 'Lượt làm kiểm tra',
  questions: 'Câu hỏi',
  materials: 'Học liệu',
  users: 'Tài khoản',
  students: 'Sinh viên',
  classes: 'Lớp học phần',
  semesters: 'Học kỳ',
  sessions: 'Buổi học',
  attendance_records: 'Điểm danh',
}

const fieldLabels: Record<string, string> = {
  old: 'Trước thay đổi',
  new: 'Sau thay đổi',
  old_score: 'Điểm cũ',
  new_score: 'Điểm mới',
  score: 'Điểm',
  weight: 'Trọng số',
  type: 'Loại',
  ref_id: 'Nguồn tham chiếu',
  assignment_id: 'Bài tập',
  question_id: 'Câu hỏi',
  class_code: 'Mã lớp',
  class_id: 'Lớp',
  code: 'Mã lớp',
  count: 'Số lượng',
  date: 'Ngày học',
  name: 'Tên',
  new_status: 'Trạng thái mới',
  note: 'Lý do',
  old_status: 'Trạng thái cũ',
  reason: 'Lý do',
  result: 'Kết quả',
  session_id: 'Buổi học',
  session_no: 'Số buổi',
  skipped: 'Bỏ qua',
  status: 'Trạng thái',
  student_id: 'Sinh viên',
  updated_fields: 'Trường đã cập nhật',
  username: 'Tên đăng nhập',
}

const statusLabels: Record<string, string> = {
  present: 'Có mặt',
  late: 'Đi trễ',
  absent: 'Vắng',
  excused: 'Có phép',
  draft: 'Nháp',
  active: 'Đang hoạt động',
  closed: 'Đã đóng',
  scheduled: 'Sắp diễn ra',
  open: 'Đang mở',
  success: 'Thành công',
  failed: 'Thất bại',
}

const getActionLabel = (action: string) => actionLabels[action] || action.replace(/_/g, ' ').toLowerCase()
const getEntityLabel = (entity: string) => entityLabels[entity] || entity

const getActionBadgeClass = (action: string) => {
  if (action === 'LOGIN') return 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300'
  if (action.startsWith('CREATE') || action.startsWith('PUBLISH') || action === 'CHECK_IN_STUDENT') {
    return 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300'
  }
  if (action.startsWith('UPDATE') || action.startsWith('PATCH') || action.startsWith('GRADE')) {
    return 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300'
  }
  if (action.startsWith('DELETE') || action.startsWith('CLOSE') || action.startsWith('RESET')) {
    return 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950 dark:text-rose-300'
  }
  return 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300'
}

const formatValue = (key: string, value: unknown): string => {
  if (typeof value === 'string') return statusLabels[value] || value
  if (typeof value === 'boolean') return value ? 'Có' : 'Không'
  if (Array.isArray(value)) return value.map((item) => formatValue(key, item)).join(', ')
  if (value && typeof value === 'object') {
    return Object.entries(value as AuditDetail)
      .map(([nestedKey, nestedValue]) => `${fieldLabels[nestedKey] || nestedKey}: ${formatValue(nestedKey, nestedValue)}`)
      .join('; ')
  }
  return value === null || value === undefined ? 'Chưa có' : String(value)
}

const getSummary = (action: string, detail: AuditDetail | null | undefined): string => {
  if (!detail) return 'Không có thông tin bổ sung'
  switch (action) {
    case 'TOGGLE_USER_STATUS':
      return typeof detail.summary === 'string'
        ? detail.summary
        : `Thay đổi trạng thái tài khoản ${String(detail.target_username || '')}`
    case 'RESET_PASSWORD':
      return typeof detail.summary === 'string'
        ? detail.summary
        : `Reset mật khẩu cho ${String(detail.target_username || '')}`
    case 'IMPORT_STUDENTS':
      return `Import: tạo ${detail.created || 0}, bỏ qua ${detail.skipped || 0}, lỗi ${detail.errors || 0}`
    case 'LOGIN':
      return detail.result === 'success' ? 'Đăng nhập thành công' : `Đăng nhập thất bại: ${detail.reason || ''}`
    case 'CHANGE_PASSWORD':
      return 'Đổi mật khẩu thành công'
    case 'PATCH_ATTENDANCE':
      return `Cập nhật điểm danh sinh viên #${detail.student_id ?? '-'}: ${formatValue('old_status', detail.old_status)} → ${formatValue('new_status', detail.new_status)}${detail.note ? `. Lý do: ${detail.note}` : ''}`
    case 'CHECK_IN_STUDENT':
      return `Ghi nhận điểm danh sinh viên #${detail.student_id ?? '-'}: ${formatValue('new_status', detail.new_status)}`
    case 'BULK_PATCH_ATTENDANCE':
    case 'MARK_REMAINING_ATTENDANCE':
      return `Cập nhật ${detail.count ?? 0} bản ghi điểm danh thành ${formatValue('status', detail.status)}`
    case 'OPEN_SESSION':
    case 'CLOSE_SESSION':
    case 'REOPEN_SESSION':
    case 'AUTO_CLOSE_SESSION':
      return `${getActionLabel(action)}${detail.class_code ? ` lớp ${detail.class_code}` : ''}${detail.session_no ? `, buổi ${detail.session_no}` : ''}`
    default:
      return typeof detail.summary === 'string' ? detail.summary : `Đã ghi nhận thao tác: ${getActionLabel(action)}`
  }
}

const toAuditDetail = (detail: AuditLog['detail']): AuditDetail | undefined => {
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) return detail as AuditDetail
  if (typeof detail === 'string') {
    try {
      const parsed = JSON.parse(detail)
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as AuditDetail) : undefined
    } catch {
      return undefined
    }
  }
  return undefined
}

const getDetailEntries = (detail: AuditDetail | null | undefined) => {
  if (!detail) return []
  return Object.entries(detail).filter(([key, value]) => key !== 'summary' && value !== undefined && value !== '')
}

export function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [action, setAction] = useState('')
  const [entity, setEntity] = useState('')
  const [performer, setPerformer] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [selected, setSelected] = useState<AuditLog | null>(null)
  const request = useRef(0)

  const load = useCallback(async () => {
    const version = ++request.current
    setLoading(true)
    setError('')
    try {
      const data = await auditApi.getLogs({
        page,
        page_size: 20,
        action: action || undefined,
        entity: entity || undefined,
        performer: performer || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      })
      if (version === request.current) {
        setLogs(data.items)
        setTotal(data.total)
      }
    } catch (cause) {
      if (version === request.current) {
        setError(getApiErrorMessage(cause, 'Không tải được nhật ký. Hãy kiểm tra kết nối.'))
      }
    } finally {
      if (version === request.current) setLoading(false)
    }
  }, [page, action, entity, performer, dateFrom, dateTo])

  useEffect(() => {
    void load()
    return () => {
      request.current++
    }
  }, [load])

  const time = (value: string) =>
    new Intl.DateTimeFormat('vi-VN', {
      timeZone: 'Asia/Ho_Chi_Minh',
      dateStyle: 'short',
      timeStyle: 'medium',
    }).format(new Date(value))

  const handleResetFilters = () => {
    setAction('')
    setEntity('')
    setPerformer('')
    setDateFrom('')
    setDateTo('')
    setPage(1)
  }

  return (
    <main className="min-w-0 space-y-6">

      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-2 border-b border-border/60">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">
            Giám sát an toàn & Truy vết hoạt động
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight flex items-center gap-2">
            <ScrollText className="h-6 w-6 text-primary" />
            Nhật ký hệ thống
          </h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Lưu vết toàn bộ thao tác quan trọng theo múi giờ Việt Nam (Asia/Ho_Chi_Minh). Thông tin xác thực nhạy cảm được che an toàn.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs font-semibold px-2.5 py-1">
            Tổng: {total} bản ghi
          </Badge>
          <Button variant="outline" size="sm" onClick={() => void load()} className="gap-1.5 text-xs">
            <RotateCcw className="h-3.5 w-3.5" /> Làm mới
          </Button>
        </div>
      </div>

      <Card className="border-border/80 shadow-2xs">
        <CardHeader className="pb-3 flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Filter className="h-4 w-4 text-primary" />
            Bộ lọc nhật ký thao tác
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleResetFilters}
            className="text-xs text-muted-foreground hover:text-foreground gap-1 h-8"
          >
            <RotateCcw className="h-3 w-3" /> Xóa bộ lọc
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="audit-action" className="text-xs font-semibold">Thao tác</Label>
              <select
                id="audit-action"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={action}
                onChange={(e) => {
                  setAction(e.target.value)
                  setPage(1)
                }}
              >
                <option value="">-- Tất cả thao tác --</option>
                {Object.entries({
                  ...Object.fromEntries(logs.map((log) => [log.action, getActionLabel(log.action)])),
                  ...actionLabels,
                }).map(([key, text]) => (
                  <option key={key} value={key}>
                    {text}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="audit-entity" className="text-xs font-semibold">Nhóm dữ liệu</Label>
              <select
                id="audit-entity"
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={entity}
                onChange={(e) => {
                  setEntity(e.target.value)
                  setPage(1)
                }}
              >
                <option value="">-- Tất cả nhóm đối tượng --</option>
                {Object.entries(entityLabels).map(([key, text]) => (
                  <option key={key} value={key}>
                    {text}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="audit-performer" className="text-xs font-semibold">Người thực hiện</Label>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  id="audit-performer"
                  placeholder="Nhập tên đăng nhập (vd: admin, gv001)..."
                  value={performer}
                  onChange={(e) => {
                    setPerformer(e.target.value)
                    setPage(1)
                  }}
                  className="h-9 pl-8 text-xs"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="audit-from" className="text-xs font-semibold">Từ ngày (Việt Nam)</Label>
              <Input
                id="audit-from"
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value)
                  setPage(1)
                }}
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="audit-to" className="text-xs font-semibold">Đến hết ngày (Việt Nam)</Label>
              <Input
                id="audit-to"
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value)
                  setPage(1)
                }}
                className="h-9 text-xs"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <RemoteState
        loading={loading}
        error={error}
        onRetry={load}
        empty={!logs.length ? 'Không có nhật ký phù hợp với bộ lọc hiện tại. Hãy đổi khoảng ngày hoặc xóa bộ lọc.' : ''}
      />

      {!loading && !error && logs.length > 0 && (
        <div className="space-y-4">
          <div className="overflow-x-auto rounded-xl border border-border/80 bg-card shadow-2xs">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-44 font-semibold">Thời gian (VN)</TableHead>
                  <TableHead className="w-32 font-semibold">Người thực hiện</TableHead>
                  <TableHead className="w-48 font-semibold">Thao tác</TableHead>
                  <TableHead className="w-36 font-semibold">Đối tượng</TableHead>
                  <TableHead className="font-semibold">Nội dung chi tiết</TableHead>
                  <TableHead className="w-24 text-right font-semibold">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => {
                  const detail = toAuditDetail(log.detail)
                  const actionBadge = getActionBadgeClass(log.action)

                  return (
                    <TableRow key={log.id} className="hover:bg-muted/40 transition-colors">
                      <TableCell className="font-mono text-xs text-muted-foreground whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <Clock className="h-3 w-3 text-muted-foreground/80 shrink-0" />
                          <span>{time(log.created_at)}</span>
                        </div>
                      </TableCell>

                      <TableCell className="font-medium text-xs">
                        <span className="font-semibold text-foreground">{log.username || 'Hệ thống'}</span>
                        {log.ip && <span className="block text-[10px] text-muted-foreground font-mono">{log.ip}</span>}
                      </TableCell>

                      <TableCell>
                        <Badge variant="outline" className={cn('text-[11px] font-semibold whitespace-nowrap', actionBadge)}>
                          {getActionLabel(log.action)}
                        </Badge>
                      </TableCell>

                      <TableCell className="text-xs text-muted-foreground">
                        <span className="font-medium text-foreground">{getEntityLabel(log.entity)}</span>
                        <span className="ml-1 text-[11px] text-muted-foreground">#{log.entity_id || '—'}</span>
                      </TableCell>

                      <TableCell className="text-xs text-muted-foreground max-w-md">
                        <p className="line-clamp-2 leading-relaxed text-foreground/90">
                          {getSummary(log.action, detail)}
                        </p>
                      </TableCell>

                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelected(log)}
                          className="h-8 px-2 text-xs text-primary gap-1"
                        >
                          <Eye className="h-3.5 w-3.5" /> Chi tiết
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>

          <Pagination page={page} total={total} loading={loading} onChange={setPage} />
        </div>
      )}

      <Dialog open={!!selected} onOpenChange={(open) => { if (!open) setSelected(null) }}>
        <DialogContent className="max-h-[90dvh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <ScrollText className="h-5 w-5 text-primary" />
              {selected && getActionLabel(selected.action)}
            </DialogTitle>
            <DialogDescription>
              Nhật ký sự kiện #{selected?.id} · {selected && time(selected.created_at)}
            </DialogDescription>
          </DialogHeader>

          {selected && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-muted/40 border border-border/60 text-xs">
                <div>
                  <span className="text-muted-foreground">Người thực hiện: </span>
                  <strong className="text-foreground">{selected.username || 'Hệ thống'}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground">Địa chỉ IP: </span>
                  <span className="font-mono text-foreground">{selected.ip || 'Không ghi nhận'}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Đối tượng: </span>
                  <span className="text-foreground">{getEntityLabel(selected.entity)} #{selected.entity_id || '—'}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Mã thao tác: </span>
                  <span className="font-mono text-foreground">{selected.action}</span>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Dữ liệu chi tiết thao tác:
                </p>
                <div className="space-y-2">
                  {getDetailEntries(toAuditDetail(selected.detail)).map(([key, value]) => (
                    <div key={key} className="rounded-lg border border-border/80 bg-card p-3 text-xs">
                      <p className="font-semibold text-primary">{fieldLabels[key] || key}</p>
                      <p className="mt-1 whitespace-pre-wrap break-words text-foreground font-mono">
                        {formatValue(key, value)}
                      </p>
                    </div>
                  ))}
                  {getDetailEntries(toAuditDetail(selected.detail)).length === 0 && (
                    <p className="text-xs text-muted-foreground italic">Không có dữ liệu chi tiết bổ sung.</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </main>
  )
}

export default AuditLogsPage
