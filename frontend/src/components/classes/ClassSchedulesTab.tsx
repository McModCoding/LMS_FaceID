import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Calendar,
  Clock,
  PlusCircle,
  Pencil,
  Trash2,
  XCircle,
  AlertCircle,
  CalendarPlus,
} from 'lucide-react'
import dayjs from 'dayjs'
import { toast } from 'sonner'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'

import { Class } from '../../types/class'
import { Schedule, ScheduleCreateDTO } from '../../types/schedule'
import { Session, SessionMakeupCreateDTO, SessionUpdateDTO } from '../../types/session'
import { ConflictItem } from '../../types/conflict'
import { classesApi } from '../../api/classes'
import { sessionsApi } from '../../api/sessions'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
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
  DialogFooter,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ConflictDialog } from '../common/ConflictDialog'
import { cn } from '@/lib/utils'
import { SessionStatusBadge } from '@/components/common/status-badge'
import { getApiErrorMessage } from '@/lib/api-error'

interface ClassSchedulesTabProps {
  classData: Class
  canManage: boolean
  onClassUpdated?: () => void
}

const WEEKDAY_OPTIONS = [
  { value: '0', label: 'Thứ Hai' },
  { value: '1', label: 'Thứ Ba' },
  { value: '2', label: 'Thứ Tư' },
  { value: '3', label: 'Thứ Năm' },
  { value: '4', label: 'Thứ Sáu' },
  { value: '5', label: 'Thứ Bảy' },
  { value: '6', label: 'Chủ Nhật' },
]

// Schedule Schema
const scheduleSchema = z
  .object({
    weekday: z.string().min(1, 'Vui lòng chọn thứ trong tuần'),
    start_time: z.string().min(1, 'Vui lòng nhập giờ bắt đầu'),
    end_time: z.string().min(1, 'Vui lòng nhập giờ kết thúc'),
    room: z.string().min(1, 'Vui lòng nhập phòng học'),
    start_date: z.string().min(1, 'Vui lòng chọn ngày bắt đầu'),
    end_date: z.string().min(1, 'Vui lòng chọn ngày kết thúc'),
  })
  .refine((data) => data.start_time < data.end_time, {
    message: 'Giờ bắt đầu phải trước giờ kết thúc',
    path: ['end_time'],
  })
  .refine((data) => data.start_date <= data.end_date, {
    message: 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc',
    path: ['end_date'],
  })

// Makeup Session Schema
const makeupSessionSchema = z
  .object({
    date: z.string().min(1, 'Vui lòng chọn ngày'),
    start_time: z.string().min(1, 'Vui lòng nhập giờ bắt đầu'),
    end_time: z.string().min(1, 'Vui lòng nhập giờ kết thúc'),
    room: z.string().min(1, 'Vui lòng nhập phòng học'),
  })
  .refine((data) => data.start_time < data.end_time, {
    message: 'Giờ bắt đầu phải trước giờ kết thúc',
    path: ['end_time'],
  })

// Edit Session Schema
const editSessionSchema = z
  .object({
    date: z.string().min(1, 'Vui lòng chọn ngày'),
    start_time: z.string().min(1, 'Vui lòng nhập giờ bắt đầu'),
    end_time: z.string().min(1, 'Vui lòng nhập giờ kết thúc'),
    room: z.string().min(1, 'Vui lòng nhập phòng học'),
  })
  .refine((data) => data.start_time < data.end_time, {
    message: 'Giờ bắt đầu phải trước giờ kết thúc',
    path: ['end_time'],
  })

export const ClassSchedulesTab: React.FC<ClassSchedulesTabProps> = ({
  classData,
  canManage,
  onClassUpdated,
}) => {
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [loadingSchedules, setLoadingSchedules] = useState(true)
  const [loadingSessions, setLoadingSessions] = useState(true)
  const [scheduleError, setScheduleError] = useState('')
  const [sessionError, setSessionError] = useState('')
  const [sessionTotal, setSessionTotal] = useState<number | null>(null)
  const [sessionPage, setSessionPage] = useState(1)
  const sessionRequestId = useRef(0)
  const sessionPageSize = 20

  // Conflict Dialog
  const [conflictDialogOpen, setConflictDialogOpen] = useState(false)
  const [conflicts, setConflicts] = useState<ConflictItem[]>([])
  const [conflictMessage, setConflictMessage] = useState('')

  // Schedule Modal
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null)
  const [deleteScheduleConfirm, setDeleteScheduleConfirm] = useState<Schedule | null>(null)

  // Makeup Session Modal
  const [isMakeupModalOpen, setIsMakeupModalOpen] = useState(false)

  // Edit Single Session Modal
  const [isEditSessionModalOpen, setIsEditSessionModalOpen] = useState(false)
  const [editingSession, setEditingSession] = useState<Session | null>(null)

  // Cancel Session Confirm
  const [cancelSessionConfirm, setCancelSessionConfirm] = useState<Session | null>(null)

  // React Hook Form for Schedule
  const scheduleForm = useForm<z.infer<typeof scheduleSchema>>({
    resolver: zodResolver(scheduleSchema),
  })

  // React Hook Form for Makeup Session
  const makeupForm = useForm<z.infer<typeof makeupSessionSchema>>({
    resolver: zodResolver(makeupSessionSchema),
  })

  // React Hook Form for Edit Session
  const editSessionForm = useForm<z.infer<typeof editSessionSchema>>({
    resolver: zodResolver(editSessionSchema),
  })

  const fetchSchedules = useCallback(async () => {
    setLoadingSchedules(true)
    setScheduleError('')
    try {
      const data = await classesApi.getSchedules(classData.id)
      setSchedules(data)
    } catch (error: unknown) {
      setScheduleError(getApiErrorMessage(error, 'Không thể tải lịch học.'))
    } finally {
      setLoadingSchedules(false)
    }
  }, [classData.id])

  const fetchSessions = useCallback(async () => {
    const requestId = ++sessionRequestId.current
    setLoadingSessions(true)
    setSessionError('')
    try {
      const data = await classesApi.getSessions(classData.id, { page: sessionPage, page_size: sessionPageSize })
      if (requestId === sessionRequestId.current) {
        setSessions(data.items)
        setSessionTotal(data.total)
      }
    } catch (error: unknown) {
      if (requestId === sessionRequestId.current) setSessionError(getApiErrorMessage(error, 'Không thể tải danh sách buổi học.'))
    } finally {
      if (requestId === sessionRequestId.current) setLoadingSessions(false)
    }
  }, [classData.id, sessionPage])

  useEffect(() => {
    void fetchSchedules()
  }, [fetchSchedules])
  useEffect(() => {
    void fetchSessions()
    return () => { sessionRequestId.current += 1 }
  }, [fetchSessions])

  const handleOpenAddSchedule = () => {
    setEditingSchedule(null)
    scheduleForm.reset({
      weekday: '0',
      start_time: '07:30',
      end_time: '11:30',
      room: '',
      start_date: dayjs().format('YYYY-MM-DD'),
      end_date: dayjs().add(90, 'day').format('YYYY-MM-DD'),
    })
    setIsScheduleModalOpen(true)
  }

  const handleOpenEditSchedule = (sch: Schedule) => {
    setEditingSchedule(sch)
    scheduleForm.reset({
      weekday: sch.weekday.toString(),
      start_time: sch.start_time.slice(0, 5),
      end_time: sch.end_time.slice(0, 5),
      room: sch.room,
      start_date: sch.start_date,
      end_date: sch.end_date,
    })
    setIsScheduleModalOpen(true)
  }

  const handleScheduleSubmit = async (values: z.infer<typeof scheduleSchema>) => {
    try {
      const payload: ScheduleCreateDTO = {
        weekday: parseInt(values.weekday, 10),
        start_time: values.start_time.length === 5 ? `${values.start_time}:00` : values.start_time,
        end_time: values.end_time.length === 5 ? `${values.end_time}:00` : values.end_time,
        room: values.room.trim().toUpperCase(),
        start_date: values.start_date,
        end_date: values.end_date,
      }

      if (editingSchedule) {
        await classesApi.updateSchedule(classData.id, editingSchedule.id, payload)
        toast.success('Cập nhật lịch học thành công')
      } else {
        await classesApi.createSchedule(classData.id, payload)
        toast.success('Thêm lịch học và sinh buổi học thành công')
      }
      setIsScheduleModalOpen(false)
      fetchSchedules()
      fetchSessions()
      onClassUpdated?.()
    } catch (error: unknown) {
      const errData = (error as any)?.response?.data
      const conflictItems = errData?.detail?.details?.conflicts ?? errData?.detail?.conflicts
      if (errData?.detail?.code === 'SCHEDULE_CONFLICT' && conflictItems?.length) {
        setConflicts(conflictItems)
        setConflictMessage(errData.detail.message || 'Phát hiện xung đột lịch học:')
        setConflictDialogOpen(true)
      } else {
        const msg = errData?.detail?.message || errData?.error?.message || 'Có lỗi xảy ra khi lưu lịch học'
        toast.error(msg)
      }
    }
  }

  const handleDeleteSchedule = async () => {
    if (!deleteScheduleConfirm) return
    try {
      await classesApi.deleteSchedule(classData.id, deleteScheduleConfirm.id)
      toast.success('Xóa lịch học thành công')
      setDeleteScheduleConfirm(null)
      fetchSchedules()
      fetchSessions()
      onClassUpdated?.()
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.error?.message || 'Không thể xóa lịch học'
      toast.error(msg)
    }
  }

  // Makeup session submit
  const handleMakeupSubmit = async (values: z.infer<typeof makeupSessionSchema>) => {
    try {
      const payload: SessionMakeupCreateDTO = {
        date: values.date,
        start_time: values.start_time.length === 5 ? `${values.start_time}:00` : values.start_time,
        end_time: values.end_time.length === 5 ? `${values.end_time}:00` : values.end_time,
        room: values.room.trim().toUpperCase(),
      }
      await classesApi.createMakeupSession(classData.id, payload)
      toast.success('Đã thêm buổi học bù thành công')
      setIsMakeupModalOpen(false)
      fetchSessions()
    } catch (error: unknown) {
      const errData = (error as any)?.response?.data
      const conflictItems = errData?.detail?.details?.conflicts ?? errData?.detail?.conflicts
      if (errData?.detail?.code === 'SCHEDULE_CONFLICT' && conflictItems?.length) {
        setConflicts(conflictItems)
        setConflictMessage(errData.detail.message || 'Buổi bù bị xung đột lịch:')
        setConflictDialogOpen(true)
      } else {
        const msg = errData?.detail?.message || errData?.error?.message || 'Không thể thêm buổi bù'
        toast.error(msg)
      }
    }
  }

  // Edit single session
  const handleOpenEditSession = (sess: Session) => {
    setEditingSession(sess)
    editSessionForm.reset({
      date: sess.date,
      start_time: sess.start_time.slice(0, 5),
      end_time: sess.end_time.slice(0, 5),
      room: sess.room,
    })
    setIsEditSessionModalOpen(true)
  }

  const handleEditSessionSubmit = async (values: z.infer<typeof editSessionSchema>) => {
    if (!editingSession) return
    try {
      const payload: SessionUpdateDTO = {
        date: values.date,
        start_time: values.start_time.length === 5 ? `${values.start_time}:00` : values.start_time,
        end_time: values.end_time.length === 5 ? `${values.end_time}:00` : values.end_time,
        room: values.room.trim().toUpperCase(),
      }
      await sessionsApi.update(editingSession.id, payload)
      toast.success('Cập nhật buổi học thành công')
      setIsEditSessionModalOpen(false)
      fetchSessions()
    } catch (error: unknown) {
      const errData = (error as any)?.response?.data
      const conflictItems = errData?.detail?.details?.conflicts ?? errData?.detail?.conflicts
      if (errData?.detail?.code === 'SCHEDULE_CONFLICT' && conflictItems?.length) {
        setConflicts(conflictItems)
        setConflictMessage(errData.detail.message || 'Buổi học bị xung đột lịch:')
        setConflictDialogOpen(true)
      } else {
        const msg = errData?.detail?.message || errData?.error?.message || 'Không thể cập nhật buổi học'
        toast.error(msg)
      }
    }
  }

  // Cancel single session
  const handleCancelSession = async () => {
    if (!cancelSessionConfirm) return
    try {
      await sessionsApi.cancel(cancelSessionConfirm.id)
      toast.success('Đã hủy buổi học')
      setCancelSessionConfirm(null)
      fetchSessions()
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.error?.message || 'Không thể hủy buổi học'
      toast.error(msg)
    }
  }

  const isClassClosed = classData.status === 'closed'

  return (
    <div className="space-y-6">

      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/60">
          <div>
            <div className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-primary" />
              <h3 className="text-base font-semibold text-foreground">Lịch học định kỳ hằng tuần</h3>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Khung giờ học định kỳ trong tuần và phân bổ phòng học áp dụng suốt học kỳ
            </p>
          </div>
          {canManage && !isClassClosed && (
            <Button size="sm" onClick={handleOpenAddSchedule} className="shrink-0 gap-1.5 self-start sm:self-auto">
              <PlusCircle className="h-4 w-4" /> Thêm lịch học
            </Button>
          )}
        </div>

        {loadingSchedules ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : scheduleError ? (
          <div role="alert" className="rounded-lg border p-4"><p>{scheduleError}</p><Button variant="outline" size="sm" className="mt-2" onClick={() => void fetchSchedules()}>Thử lại</Button></div>
        ) : schedules.length === 0 ? (
          <div className="text-center py-6 text-sm text-muted-foreground border rounded-lg bg-card">
            Chưa thiết lập lịch học định kỳ nào cho lớp này.
          </div>
        ) : (
          <div className="rounded-md border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Thứ</TableHead>
                  <TableHead>Thời gian</TableHead>
                  <TableHead>Phòng học</TableHead>
                  <TableHead>Khoảng thời gian áp dụng</TableHead>
                  {canManage && !isClassClosed && <TableHead className="text-right">Thao tác</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {schedules.map((sch) => {
                  const weekdayName = WEEKDAY_OPTIONS.find((o) => o.value === sch.weekday.toString())?.label || `Thứ ${sch.weekday + 2}`
                  return (
                    <TableRow key={sch.id}>
                      <TableCell className="font-semibold">{weekdayName}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>
                            {sch.start_time.slice(0, 5)} - {sch.end_time.slice(0, 5)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="font-medium">{sch.room}</TableCell>
                      <TableCell>
                        {dayjs(sch.start_date).format('DD/MM/YYYY')} — {dayjs(sch.end_date).format('DD/MM/YYYY')}
                      </TableCell>
                      {canManage && !isClassClosed && (
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="sm" onClick={() => handleOpenEditSchedule(sch)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              onClick={() => setDeleteScheduleConfirm(sch)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      )}
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      <div className="space-y-4 pt-5 border-t border-border/70">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/60">
          <div>
            <div className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-primary" />
              <h3 className="text-base font-semibold text-foreground">
                Danh sách các buổi học chi tiết{!loadingSessions && !sessionError && sessionTotal !== null ? ` (${sessionTotal} buổi)` : ''}
              </h3>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Các buổi học được sinh tự động theo lịch định kỳ hoặc thêm bổ sung (buổi bù)
            </p>
          </div>
          {canManage && !isClassClosed && (
            <Button variant="outline" size="sm" onClick={() => setIsMakeupModalOpen(true)} className="shrink-0 gap-1.5 self-start sm:self-auto">
              <CalendarPlus className="h-4 w-4" /> Thêm buổi bù
            </Button>
          )}
        </div>

        {loadingSessions ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : sessionError ? (
          <div role="alert" className="rounded-lg border p-4"><p>{sessionError}</p><Button variant="outline" size="sm" className="mt-2" onClick={() => void fetchSessions()}>Thử lại</Button></div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground border rounded-lg bg-card">
            {sessionTotal ? 'Không có buổi học ở trang này. Hãy quay lại trang trước.' : 'Chưa có buổi học nào. Buổi học sẽ được tự động sinh khi thêm lịch học định kỳ hoặc thêm buổi bù.'}
          </div>
        ) : (
          <div className="rounded-md border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16 text-center">Buổi #</TableHead>
                  <TableHead>Ngày học</TableHead>
                  <TableHead>Giờ học</TableHead>
                  <TableHead>Phòng</TableHead>
                  <TableHead>Loại</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  {canManage && !isClassClosed && <TableHead className="text-right">Thao tác</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.map((sess) => {
                  const isCancelled = sess.status === 'cancelled'
                  const isScheduled = sess.status === 'scheduled'

                  return (
                    <TableRow key={sess.id} className={cn(isCancelled && 'opacity-60 bg-muted/30')}>
                      <TableCell className="text-center font-bold">{sess.session_no}</TableCell>
                      <TableCell className={cn(isCancelled && 'line-through')}>
                        {dayjs(sess.date).format('DD/MM/YYYY')}
                      </TableCell>
                      <TableCell className={cn(isCancelled && 'line-through')}>
                        {sess.start_time.slice(0, 5)} - {sess.end_time.slice(0, 5)}
                      </TableCell>
                      <TableCell className={cn('font-medium', isCancelled && 'line-through')}>{sess.room}</TableCell>
                      <TableCell>
                        {sess.schedule_id ? (
                          <span className="text-xs text-muted-foreground">Theo lịch</span>
                        ) : (
                          <Badge variant="outline" className="text-xs text-primary border-primary">
                            Buổi bù
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell><SessionStatusBadge status={sess.status} /></TableCell>
                      {canManage && !isClassClosed && (
                        <TableCell className="text-right">
                          {isScheduled && (
                            <div className="flex justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                aria-label={`Sửa buổi ${sess.session_no}`}
                                onClick={() => handleOpenEditSession(sess)}
                                title="Sửa ngày/giờ/phòng"
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:text-destructive"
                                aria-label={`Hủy buổi ${sess.session_no}`}
                                onClick={() => setCancelSessionConfirm(sess)}
                                title="Hủy buổi"
                              >
                                <XCircle className="h-4 w-4" />
                              </Button>
                            </div>
                          )}
                        </TableCell>
                      )}
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
        {!loadingSessions && !sessionError && sessionTotal !== null && sessionTotal > sessionPageSize && <div className="flex flex-wrap items-center justify-end gap-2 text-sm"><Button variant="outline" size="sm" disabled={sessionPage <= 1} onClick={() => setSessionPage((page) => page - 1)}>Trước</Button><span>Trang {sessionPage} / {Math.ceil(sessionTotal / sessionPageSize)}</span><Button variant="outline" size="sm" disabled={sessionPage * sessionPageSize >= sessionTotal} onClick={() => setSessionPage((page) => page + 1)}>Sau</Button></div>}
      </div>

      <Dialog open={isScheduleModalOpen} onOpenChange={setIsScheduleModalOpen}>
        <DialogContent className="max-w-md">
          <form onSubmit={scheduleForm.handleSubmit(handleScheduleSubmit)}>
            <DialogHeader>
              <DialogTitle>{editingSchedule ? 'Chỉnh sửa Lịch học' : 'Thêm Lịch học mới'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Thứ trong tuần</Label>
                <Controller
                  control={scheduleForm.control}
                  name="weekday"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue placeholder="Chọn thứ" />
                      </SelectTrigger>
                      <SelectContent>
                        {WEEKDAY_OPTIONS.map((o) => (
                          <SelectItem key={o.value} value={o.value}>
                            {o.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Giờ bắt đầu</Label>
                  <Input type="time" {...scheduleForm.register('start_time')} />
                  {scheduleForm.formState.errors.start_time && (
                    <p className="text-xs text-destructive">{scheduleForm.formState.errors.start_time.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label>Giờ kết thúc</Label>
                  <Input type="time" {...scheduleForm.register('end_time')} />
                  {scheduleForm.formState.errors.end_time && (
                    <p className="text-xs text-destructive">{scheduleForm.formState.errors.end_time.message}</p>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label>Phòng học</Label>
                <Input placeholder="Ví dụ: A101, B204..." {...scheduleForm.register('room')} />
                {scheduleForm.formState.errors.room && (
                  <p className="text-xs text-destructive">{scheduleForm.formState.errors.room.message}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Ngày bắt đầu</Label>
                  <Input type="date" {...scheduleForm.register('start_date')} />
                  {scheduleForm.formState.errors.start_date && (
                    <p className="text-xs text-destructive">{scheduleForm.formState.errors.start_date.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label>Ngày kết thúc</Label>
                  <Input type="date" {...scheduleForm.register('end_date')} />
                  {scheduleForm.formState.errors.end_date && (
                    <p className="text-xs text-destructive">{scheduleForm.formState.errors.end_date.message}</p>
                  )}
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsScheduleModalOpen(false)}>
                Hủy
              </Button>
              <Button type="submit" disabled={scheduleForm.formState.isSubmitting}>
                {editingSchedule ? 'Lưu thay đổi' : 'Tạo lịch & Sinh buổi'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={isMakeupModalOpen} onOpenChange={setIsMakeupModalOpen}>
        <DialogContent className="max-w-md">
          <form onSubmit={makeupForm.handleSubmit(handleMakeupSubmit)}>
            <DialogHeader>
              <DialogTitle>Thêm Buổi học bù</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Ngày học bù</Label>
                <Input type="date" {...makeupForm.register('date')} />
                {makeupForm.formState.errors.date && (
                  <p className="text-xs text-destructive">{makeupForm.formState.errors.date.message}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Giờ bắt đầu</Label>
                  <Input type="time" {...makeupForm.register('start_time')} />
                  {makeupForm.formState.errors.start_time && (
                    <p className="text-xs text-destructive">{makeupForm.formState.errors.start_time.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label>Giờ kết thúc</Label>
                  <Input type="time" {...makeupForm.register('end_time')} />
                  {makeupForm.formState.errors.end_time && (
                    <p className="text-xs text-destructive">{makeupForm.formState.errors.end_time.message}</p>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label>Phòng học</Label>
                <Input placeholder="Ví dụ: A101" {...makeupForm.register('room')} />
                {makeupForm.formState.errors.room && (
                  <p className="text-xs text-destructive">{makeupForm.formState.errors.room.message}</p>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsMakeupModalOpen(false)}>
                Hủy
              </Button>
              <Button type="submit" disabled={makeupForm.formState.isSubmitting}>
                Tạo buổi bù
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={isEditSessionModalOpen} onOpenChange={setIsEditSessionModalOpen}>
        <DialogContent className="max-w-md">
          <form onSubmit={editSessionForm.handleSubmit(handleEditSessionSubmit)}>
            <DialogHeader>
              <DialogTitle>Chỉnh sửa Buổi #{editingSession?.session_no}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Ngày học</Label>
                <Input type="date" {...editSessionForm.register('date')} />
                {editSessionForm.formState.errors.date && (
                  <p className="text-xs text-destructive">{editSessionForm.formState.errors.date.message}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Giờ bắt đầu</Label>
                  <Input type="time" {...editSessionForm.register('start_time')} />
                  {editSessionForm.formState.errors.start_time && (
                    <p className="text-xs text-destructive">{editSessionForm.formState.errors.start_time.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label>Giờ kết thúc</Label>
                  <Input type="time" {...editSessionForm.register('end_time')} />
                  {editSessionForm.formState.errors.end_time && (
                    <p className="text-xs text-destructive">{editSessionForm.formState.errors.end_time.message}</p>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label>Phòng học</Label>
                <Input placeholder="Ví dụ: A101" {...editSessionForm.register('room')} />
                {editSessionForm.formState.errors.room && (
                  <p className="text-xs text-destructive">{editSessionForm.formState.errors.room.message}</p>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsEditSessionModalOpen(false)}>
                Hủy
              </Button>
              <Button type="submit" disabled={editSessionForm.formState.isSubmitting}>
                Lưu thay đổi
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteScheduleConfirm} onOpenChange={(o) => !o && setDeleteScheduleConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-destructive" />
              Xác nhận xóa lịch học
            </AlertDialogTitle>
            <AlertDialogDescription>
              Hành động này sẽ xóa các buổi học <strong>chưa diễn ra (scheduled)</strong> thuộc lịch học này. Các buổi đã mở hoặc đã đóng sẽ được giữ nguyên.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDeleteSchedule}
            >
              Xóa lịch học
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!cancelSessionConfirm} onOpenChange={(o) => !o && setCancelSessionConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-destructive" />
              Xác nhận hủy buổi học #{cancelSessionConfirm?.session_no}
            </AlertDialogTitle>
            <AlertDialogDescription>
              Buổi học vào ngày <strong>{cancelSessionConfirm && dayjs(cancelSessionConfirm.date).format('DD/MM/YYYY')}</strong> sẽ được đánh dấu là <strong>Đã hủy</strong> và không tính vào chuyên cần sau này.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Bỏ qua</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleCancelSession}
            >
              Hủy buổi học
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <ConflictDialog
        open={conflictDialogOpen}
        onOpenChange={setConflictDialogOpen}
        conflicts={conflicts}
        message={conflictMessage}
      />
    </div>
  )
}
