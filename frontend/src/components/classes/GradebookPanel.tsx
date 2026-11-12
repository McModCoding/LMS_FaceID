import React, { useCallback, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Award,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Plus,
  Pencil,
  Trash2,
  X,
  Layers,
  Sparkles,
  ExternalLink,
} from 'lucide-react'
import { api } from '@/api/client'
import { RemoteState, Pagination } from '@/components/common/RemoteState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
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
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from '@/components/ui/alert-dialog'
import { cn } from '@/lib/utils'
import { getApiErrorMessage } from '@/lib/api-error'

interface Component {
  id: number
  name: string
  type: string
  weight: string
  ref_id: number | null
  source_name: string
}

interface Row {
  student_id: number
  student_code: string
  student_name: string
  is_dropped: boolean
  values: { component_id: number; score: string | null }[]
  missing_count: number
  total_score: string
}

interface Book {
  published: boolean
  weight_total: string | null
  components: Component[]
  items: Row[]
  total: number
  message: string
}

const types: Record<string, string> = {
  attendance: 'Chuyên cần',
  assignment: 'Bài tập',
  exam: 'Kiểm tra',
  manual: 'Nhập tay',
}

const typeColors: Record<string, string> = {
  attendance: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800',
  assignment: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800',
  exam: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-800',
  manual: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800',
}

export function GradebookPanel({
  classId,
  student = false,
  writable = true,
}: {
  classId: number
  student?: boolean
  writable?: boolean
}) {
  const base = `/classes/${classId}/gradebook`
  const location = useLocation()

  const [data, setData] = useState<Book | null>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const [confirmPublish, setConfirmPublish] = useState(false)
  const [showConfigForm, setShowConfigForm] = useState(false)

  // Component form state
  const [name, setName] = useState('')
  const [weight, setWeight] = useState('')
  const [type, setType] = useState('attendance')
  const [refId, setRefId] = useState('')
  const [editing, setEditing] = useState<Component | null>(null)

  // Sources for exam/assignment
  const [sources, setSources] = useState<{ id: number; title: string }[]>([])
  const [sourcePage, setSourcePage] = useState(1)
  const [sourceTotal, setSourceTotal] = useState(0)
  const [sourceLoading, setSourceLoading] = useState(false)
  const [sourceError, setSourceError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get<Book>(base, { params: { page, page_size: 20 } })
      setData(res.data)
    } catch (cause) {
      setError(getApiErrorMessage(cause, 'Không tải được bảng điểm.'))
    } finally {
      setLoading(false)
    }
  }, [base, page])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (student || !['assignment', 'exam'].includes(type)) {
      setSources([])
      return
    }
    let active = true
    setSourceLoading(true)
    setSourceError('')
    api
      .get(`/classes/${classId}/${type === 'assignment' ? 'assignments' : 'exams'}`, {
        params: { page: sourcePage, page_size: 20 },
      })
      .then((response) => {
        if (active) {
          setSources(response.data.items.filter((r: { status: string }) => r.status !== 'draft'))
          setSourceTotal(response.data.total)
        }
      })
      .catch((cause) => {
        if (active) setSourceError(getApiErrorMessage(cause, 'Không tải được nguồn điểm.'))
      })
      .finally(() => {
        if (active) setSourceLoading(false)
      })
    return () => {
      active = false
    }
  }, [classId, type, sourcePage, student])

  async function mutate(action: () => Promise<unknown>) {
    setBusy(true)
    setActionError('')
    try {
      await action()
      await load()
      return true
    } catch (cause) {
      setActionError(getApiErrorMessage(cause, 'Không lưu được thay đổi.'))
      return false
    } finally {
      setBusy(false)
    }
  }

  const handleEditComponent = (c: Component) => {
    setEditing(c)
    setName(c.name)
    setWeight(c.weight)
    setType(c.type)
    setRefId(String(c.ref_id ?? ''))
    setShowConfigForm(true)
  }

  const handleCancelEdit = () => {
    setEditing(null)
    setName('')
    setWeight('')
    setRefId('')
    setShowConfigForm(false)
  }

  const handleSaveComponent = async (e: React.FormEvent) => {
    e.preventDefault()
    const payload = {
      name,
      weight,
      type,
      ref_id: ['assignment', 'exam'].includes(type) ? Number(refId) : null,
    }
    const success = await mutate(() =>
      editing ? api.put(`${base}/components/${editing.id}`, payload) : api.post(`${base}/components`, payload)
    )
    if (success) {
      handleCancelEdit()
    }
  }

  const handleExportExcel = () => {
    void mutate(async () => {
      const response = await api.get(`${base}/export`, { responseType: 'blob' })
      const url = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `bang-diem-${classId}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    })
  }

  const weightTotalNum = data ? Number(data.weight_total ?? 0) : 0
  const isWeightValid = weightTotalNum === 100

  return (
    <Card className="min-w-0 border-border/70 shadow-xs">
      <CardHeader className="pb-4 sm:flex-row sm:items-center sm:justify-between space-y-3 sm:space-y-0">
        <div>
          <CardTitle className="text-xl flex items-center gap-2">
            <Award className="h-5 w-5 text-primary" />
            Bảng điểm tổng hợp
          </CardTitle>
          <CardDescription className="mt-1">
            {student
              ? 'Kết quả học tập và chi tiết điểm các thành phần theo trọng số'
              : 'Quản lý thành phần đánh giá, tính điểm theo trọng số và công bố kết quả cho sinh viên'}
          </CardDescription>
        </div>

        {!loading && !error && data && (
          <div className="flex flex-wrap items-center gap-2 pt-1 sm:pt-0">
            {!student && writable && (
              <Button
                variant={data.published ? 'secondary' : 'default'}
                size="sm"
                disabled={busy || !isWeightValid}
                onClick={() => setConfirmPublish(true)}
                className="gap-1.5"
              >
                <CheckCircle2 className="h-4 w-4" />
                {data.published ? 'Cập nhật công bố' : 'Công bố bảng điểm'}
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={handleExportExcel}
              className="gap-1.5"
            >
              <FileSpreadsheet className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              Xuất Excel
            </Button>
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-6">
        <RemoteState loading={loading} error={error} onRetry={load} />

        {!loading && !error && data && (
          <>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">

              <div
                className={cn(
                  'flex items-center gap-3.5 rounded-xl border p-4 transition-all',
                  data.published
                    ? 'border-emerald-200/80 bg-emerald-50/50 dark:border-emerald-900/60 dark:bg-emerald-950/20'
                    : 'border-slate-200/80 bg-slate-50/60 dark:border-slate-800 dark:bg-slate-900/40'
                )}
              >
                <div
                  className={cn(
                    'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg shadow-2xs font-semibold',
                    data.published
                      ? 'bg-emerald-500 text-white'
                      : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                  )}
                >
                  {data.published ? <CheckCircle2 className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-muted-foreground">Trạng thái công bố</p>
                  <p className="font-semibold text-sm leading-snug">
                    {data.published ? 'Đã công bố cho sinh viên' : 'Chưa công bố (Bản nháp)'}
                  </p>
                </div>
              </div>

              <div
                className={cn(
                  'flex items-center gap-3.5 rounded-xl border p-4 transition-all',
                  isWeightValid
                    ? 'border-blue-200/80 bg-blue-50/50 dark:border-blue-900/60 dark:bg-blue-950/20'
                    : 'border-amber-200/80 bg-amber-50/50 dark:border-amber-900/60 dark:bg-amber-950/20'
                )}
              >
                <div
                  className={cn(
                    'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg shadow-2xs font-bold text-sm',
                    isWeightValid
                      ? 'bg-blue-600 text-white'
                      : 'bg-amber-500 text-white'
                  )}
                >
                  %
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-muted-foreground">Tổng trọng số hiện tại</p>
                  <p className="font-semibold text-sm leading-snug">
                    {weightTotalNum}% <span className="text-xs text-muted-foreground font-normal">/ 100%</span>
                    {isWeightValid ? (
                      <span className="ml-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-medium">✓ Đạt</span>
                    ) : (
                      <span className="ml-1.5 text-xs text-amber-600 dark:text-amber-400 font-medium">Chưa đủ 100%</span>
                    )}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3.5 rounded-xl border border-border/70 bg-card p-4 shadow-2xs">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary shadow-2xs font-bold">
                  <Layers className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-muted-foreground">Số thành phần đánh giá</p>
                  <p className="font-semibold text-sm leading-snug">
                    {data.components.length} cột điểm
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-2.5 rounded-lg border border-border/60 bg-muted/40 p-3 text-xs text-muted-foreground">
              <Sparkles className="h-4 w-4 text-primary shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-foreground">{data.message}</p>
                <p className="mt-0.5">
                  Điểm chưa có được tính 0 theo trọng số. Điểm tổng hợp độc lập với quyền xem kết quả chi tiết từng bài.
                </p>
              </div>
            </div>

            {actionError && (
              <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{actionError}</span>
              </div>
            )}

            {/* PHẦN QUẢN LÝ THÀNH PHẦN ĐIỂM (Dành cho Giảng viên & Admin) */}
            {!student && writable && (
              <div className="space-y-4 rounded-xl border border-border/80 bg-muted/20 p-4 sm:p-5">
                <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-border/60">
                  <div>
                    <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                      <Layers className="h-4 w-4 text-primary" />
                      Cấu hình thành phần điểm
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Thiết lập các cột điểm và phân bổ tỷ lệ phần trăm (tổng cần đạt 100%)
                    </p>
                  </div>

                  {!showConfigForm ? (
                    <Button
                      size="sm"
                      onClick={() => setShowConfigForm(true)}
                      className="gap-1.5"
                    >
                      <Plus className="h-4 w-4" /> Thêm thành phần
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleCancelEdit}
                      className="gap-1.5 text-muted-foreground"
                    >
                      <X className="h-4 w-4" /> Đóng biểu mẫu
                    </Button>
                  )}
                </div>

                {showConfigForm && (
                  <form
                    onSubmit={handleSaveComponent}
                    className="space-y-4 rounded-lg border border-border bg-card p-4 shadow-xs animate-in fade-in-50"
                  >
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                        {editing ? <Pencil className="h-4 w-4 text-primary" /> : <Plus className="h-4 w-4 text-primary" />}
                        {editing ? 'Chỉnh sửa thành phần điểm' : 'Thêm thành phần điểm mới'}
                      </h4>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="grade-name" className="text-xs font-semibold">
                        Tên thành phần điểm <span className="text-destructive">*</span>
                      </Label>
                      <Input
                        id="grade-name"
                        required
                        maxLength={200}
                        placeholder="Ví dụ: Điểm quá trình, Chuyên cần, Kiểm tra giữa kỳ..."
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="h-9 text-sm"
                      />
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="grade-type" className="text-xs font-semibold">
                          Loại nguồn điểm <span className="text-destructive">*</span>
                        </Label>
                        <select
                          id="grade-type"
                          disabled={!!editing}
                          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-60"
                          value={type}
                          onChange={(e) => {
                            setType(e.target.value)
                            setRefId('')
                            setSourcePage(1)
                          }}
                        >
                          {Object.entries(types).map(([key, label]) => (
                            <option key={key} value={key}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="grade-weight" className="text-xs font-semibold">
                          Trọng số (%) <span className="text-destructive">*</span>
                        </Label>
                        <Input
                          id="grade-weight"
                          type="number"
                          min="0"
                          max="100"
                          step="0.0001"
                          placeholder="Ví dụ: 10, 20, 50..."
                          required
                          value={weight}
                          onChange={(e) => setWeight(e.target.value)}
                          className="h-9 text-sm"
                        />
                      </div>
                    </div>

                    {['assignment', 'exam'].includes(type) && (
                      <div className="space-y-2 rounded-lg border border-border/70 bg-muted/30 p-3">
                        <Label htmlFor="grade-source" className="text-xs font-semibold">
                          Liên kết với bài đã công bố cùng lớp <span className="text-destructive">*</span>
                        </Label>
                        <RemoteState loading={sourceLoading} error={sourceError} />
                        <select
                          id="grade-source"
                          disabled={!!editing || sourceLoading}
                          required
                          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                          value={refId}
                          onChange={(e) => setRefId(e.target.value)}
                        >
                          <option value="">-- Chọn bài kiểm tra / bài tập đã công bố --</option>
                          {sources.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.title}
                            </option>
                          ))}
                        </select>
                        <Pagination
                          page={sourcePage}
                          total={sourceTotal}
                          loading={sourceLoading}
                          onChange={setSourcePage}
                        />
                      </div>
                    )}

                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <Button size="sm" disabled={busy || sourceLoading} type="submit">
                        {editing ? 'Cập nhật thành phần' : 'Lưu thành phần'}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        type="button"
                        onClick={handleCancelEdit}
                      >
                        Hủy
                      </Button>
                    </div>
                  </form>
                )}

                {/* Danh sách các thành phần hiện tại */}
                {data.components.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border/80 bg-background/50 p-6 text-center text-sm text-muted-foreground">
                    <p>Chưa thiết lập thành phần đánh giá nào.</p>
                    <p className="text-xs mt-1">Nhấn &quot;Thêm thành phần&quot; để tạo các cột điểm chuyên cần, kiểm tra hoặc nhập tay.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-lg border border-border/80 bg-card shadow-2xs">
                    <Table>
                      <TableHeader>
                        <TableRow className="hover:bg-transparent">
                          <TableHead className="font-semibold">Tên thành phần</TableHead>
                          <TableHead className="font-semibold">Loại điểm</TableHead>
                          <TableHead className="font-semibold">Nguồn dữ liệu</TableHead>
                          <TableHead className="font-semibold text-center">Trọng số</TableHead>
                          {writable && <TableHead className="font-semibold text-right">Thao tác</TableHead>}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.components.map((c) => (
                          <TableRow key={c.id}>
                            <TableCell className="font-medium text-foreground">{c.name}</TableCell>
                            <TableCell>
                              <Badge
                                variant="outline"
                                className={cn('text-xs font-medium', typeColors[c.type] || '')}
                              >
                                {types[c.type] || c.type}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {c.source_name || '—'}
                            </TableCell>
                            <TableCell className="text-center font-semibold text-foreground">
                              {Number(c.weight)}%
                            </TableCell>
                            {writable && (
                              <TableCell className="text-right">
                                <div className="flex items-center justify-end gap-1">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    disabled={busy}
                                    onClick={() => handleEditComponent(c)}
                                    title="Sửa tên hoặc trọng số"
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    disabled={busy}
                                    className="text-destructive hover:text-destructive"
                                    onClick={() => {
                                      if (
                                        window.confirm(
                                          `Xác nhận xóa thành phần “${c.name}” và toàn bộ điểm liên quan?`
                                        )
                                      ) {
                                        void mutate(() => api.delete(`${base}/components/${c.id}`))
                                      }
                                    }}
                                    title="Xóa thành phần"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </div>
                              </TableCell>
                            )}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            )}

            {/* BẢNG ĐIỂM SINH VIÊN (Dành cho Giảng viên / Admin) */}
            {!student && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-foreground">
                      Danh sách điểm sinh viên ({data.total} sinh viên)
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Bảng điểm theo từng cột thành phần và điểm tổng kết hệ số 10
                    </p>
                  </div>
                </div>

                {data.items.length === 0 ? (
                  <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                    Chưa có sinh viên nào trong danh sách lớp.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-border/80 bg-card shadow-2xs">
                    <Table>
                      <TableHeader>
                        <TableRow className="hover:bg-transparent">
                          <TableHead className="w-28 font-semibold">Mã SV</TableHead>
                          <TableHead className="min-w-[160px] font-semibold">Họ và tên</TableHead>
                          {data.components.map((c) => (
                            <TableHead key={c.id} className="text-center font-semibold">
                              <span className="block truncate max-w-[140px]" title={c.name}>
                                {c.name}
                              </span>
                              <span className="text-[11px] font-normal text-muted-foreground">
                                ({Number(c.weight)}%)
                              </span>
                            </TableHead>
                          ))}
                          <TableHead className="text-center font-semibold w-24">Tổng kết</TableHead>
                          <TableHead className="text-right font-semibold w-32">Ghi chú</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.items.map((row) => (
                          <TableRow key={row.student_id} className={cn(row.is_dropped && 'opacity-60 bg-muted/30')}>
                            <TableCell className="font-semibold text-xs text-muted-foreground font-mono">
                              {row.student_code}
                            </TableCell>
                            <TableCell className="font-medium">
                              {row.student_name}
                              {row.is_dropped && (
                                <Badge variant="secondary" className="ml-2 text-[10px]">
                                  Đã rút
                                </Badge>
                              )}
                            </TableCell>
                            {/* Từng cột điểm thành phần */}
                            {data.components.map((c) => {
                              const val = row.values.find((v) => v.component_id === c.id)
                              const scoreNum = val?.score !== null && val?.score !== undefined ? Number(val.score) : null

                              return (
                                <TableCell key={c.id} className="text-center">
                                  {writable && c.type === 'manual' ? (
                                    <form
                                      className="inline-flex items-center gap-1"
                                      onSubmit={(event) => {
                                        event.preventDefault()
                                        const formVal = new FormData(event.currentTarget).get('score')
                                        void mutate(() =>
                                          api.put(`${base}/components/${c.id}/students/${row.student_id}`, {
                                            score: formVal === '' ? null : formVal,
                                          })
                                        )
                                      }}
                                    >
                                      <Input
                                        className="h-8 w-18 text-center text-xs"
                                        aria-label={`Điểm ${c.name} của ${row.student_code}`}
                                        name="score"
                                        type="number"
                                        min="0"
                                        max="10"
                                        step="0.01"
                                        defaultValue={scoreNum !== null ? scoreNum : ''}
                                      />
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-8 px-2 text-xs"
                                        disabled={busy}
                                        title="Lưu điểm này"
                                      >
                                        Lưu
                                      </Button>
                                    </form>
                                  ) : (
                                    <div className="inline-flex flex-col items-center">
                                      <span
                                        className={cn(
                                          'text-sm font-semibold',
                                          scoreNum === null ? 'text-muted-foreground font-normal italic' : 'text-foreground'
                                        )}
                                      >
                                        {scoreNum !== null ? scoreNum.toFixed(2) : '0.00'}
                                      </span>
                                      {c.type !== 'manual' && (
                                        <Link
                                          className="text-[11px] text-primary hover:underline inline-flex items-center gap-0.5 mt-0.5"
                                          to={`${location.pathname}?tab=${
                                            c.type === 'attendance'
                                              ? 'attendance'
                                              : c.type === 'exam'
                                              ? 'exams'
                                              : 'assignments'
                                          }`}
                                          title="Xem chi tiết tại nguồn điểm"
                                        >
                                          Xem <ExternalLink className="h-2.5 w-2.5" />
                                        </Link>
                                      )}
                                    </div>
                                  )}
                                </TableCell>
                              )
                            })}
                            {/* Điểm tổng kết */}
                            <TableCell className="text-center font-bold text-sm">
                              <Badge
                                variant={Number(row.total_score) >= 5 ? 'default' : 'destructive'}
                                className="font-semibold text-xs px-2 py-0.5"
                              >
                                {Number(row.total_score).toFixed(1)}
                              </Badge>
                            </TableCell>
                            {/* Ghi chú */}
                            <TableCell className="text-right text-xs">
                              {row.missing_count > 0 ? (
                                <span className="text-amber-600 dark:text-amber-400 font-medium">
                                  Thiếu {row.missing_count} cột
                                </span>
                              ) : (
                                <span className="text-emerald-600 dark:text-emerald-400 font-medium">Đủ điểm</span>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}

                <Pagination page={page} total={data.total} loading={loading} onChange={setPage} />
              </div>
            )}

            {/* BẢNG ĐIỂM DÀNH CHO SINH VIÊN */}
            {student && (
              <div className="space-y-4">
                {data.items.map((row) => (
                  <div key={row.student_id} className="space-y-4">
                    {/* Thẻ điểm tổng kết */}
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-xl border border-primary/20 bg-primary/5 p-5">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-primary">Điểm tổng kết môn học</p>
                        <div className="mt-1 flex items-baseline gap-2">
                          <span className="text-4xl font-extrabold text-foreground">
                            {Number(row.total_score).toFixed(1)}
                          </span>
                          <span className="text-muted-foreground font-medium text-sm">/ 10</span>
                        </div>
                      </div>

                      {row.missing_count > 0 && (
                        <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/20 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
                          <AlertCircle className="h-4 w-4 shrink-0" />
                          <span>Còn {row.missing_count} thành phần chưa có điểm (tạm tính 0).</span>
                        </div>
                      )}
                    </div>

                    {/* Chi tiết từng thành phần điểm */}
                    <div className="space-y-3">
                      <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                        <Layers className="h-4 w-4 text-primary" />
                        Chi tiết từng thành phần đánh giá
                      </h4>

                      <div className="overflow-x-auto rounded-xl border border-border/80 bg-card shadow-2xs">
                        <Table>
                          <TableHeader>
                            <TableRow className="hover:bg-transparent">
                              <TableHead className="font-semibold">Thành phần</TableHead>
                              <TableHead className="font-semibold">Loại</TableHead>
                              <TableHead className="font-semibold">Nguồn điểm</TableHead>
                              <TableHead className="text-center font-semibold">Trọng số</TableHead>
                              <TableHead className="text-right font-semibold">Điểm số</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {row.values.map((v) => {
                              const c = data.components.find((comp) => comp.id === v.component_id)
                              if (!c) return null
                              const scoreNum = v.score !== null ? Number(v.score) : null

                              return (
                                <TableRow key={v.component_id}>
                                  <TableCell className="font-medium text-foreground">{c.name}</TableCell>
                                  <TableCell>
                                    <Badge
                                      variant="outline"
                                      className={cn('text-xs font-medium', typeColors[c.type] || '')}
                                    >
                                      {types[c.type] || c.type}
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="text-sm text-muted-foreground">{c.source_name || '—'}</TableCell>
                                  <TableCell className="text-center font-semibold text-foreground">
                                    {Number(c.weight)}%
                                  </TableCell>
                                  <TableCell className="text-right font-bold text-sm">
                                    {scoreNum !== null ? (
                                      <span className="text-foreground">{scoreNum.toFixed(2)}/10</span>
                                    ) : (
                                      <span className="text-muted-foreground italic font-normal text-xs">
                                        Chưa có (tính 0)
                                      </span>
                                    )}
                                  </TableCell>
                                </TableRow>
                              )
                            })}
                          </TableBody>
                        </Table>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* Modal xác nhận công bố */}
        <AlertDialog open={confirmPublish} onOpenChange={setConfirmPublish}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Xác nhận công bố bảng điểm?</AlertDialogTitle>
              <AlertDialogDescription>
                Sinh viên trong lớp sẽ có thể xem được điểm tổng hợp của mình. Các thành phần điểm chưa có vẫn sẽ tạm tính 0 theo trọng số tương ứng và hiển thị rõ ràng. Mọi thay đổi điểm số sau khi công bố đều được lưu nhật ký hệ thống.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={busy}>Hủy</AlertDialogCancel>
              <AlertDialogAction
                disabled={busy}
                onClick={(event) => {
                  event.preventDefault()
                  void mutate(() => api.post(`${base}/publish`)).then((ok) => {
                    if (ok) setConfirmPublish(false)
                  })
                }}
              >
                Xác nhận công bố
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  )
}
