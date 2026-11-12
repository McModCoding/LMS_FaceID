import { ClassOverview } from '@/components/classes/ClassOverview'
import { GradebookPanel } from '@/components/classes/GradebookPanel'
import { LeaveRequestsPanel } from '@/components/classes/LeaveRequestsPanel'
import { MaterialsPanel } from '@/components/classes/MaterialsPanel'
import { AttendanceReportPanel } from '@/components/attendance/AttendanceReportPanel'
import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle2,
  Lock,
  Pencil,
  BookOpen,
  SlidersHorizontal,
} from 'lucide-react'
import { toast } from 'sonner'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'

import { Class, ClassUpdateDTO } from '../../../types/class'
import { classesApi } from '../../../api/classes'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent } from '@/components/ui/tabs'
import { ClassNavigation } from '@/components/classes/ClassNavigation'
import { ClassPageHeader } from '@/components/classes/ClassPageHeader'
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
import { ClassStudentsTab } from '../../../components/classes/ClassStudentsTab'
import { ClassSchedulesTab } from '../../../components/classes/ClassSchedulesTab'
import { AttendancePanel } from '../../../components/attendance/AttendancePanel'
import { AnnouncementsPanel, AssignmentsPanel, GroupsPanel } from '../../../components/classes/LearningTabs'
import { QuestionBankPanel } from '../../../components/classes/QuestionBankPanel'
import { ExamDraftPanel } from '../../../components/classes/exams/ExamDraftPanel'
import { getApiErrorMessage } from '@/lib/api-error'
import { RemoteSearchSelect } from '@/components/common/RemoteSearchSelect'
import { searchLecturers } from '@/lib/admin-search-options'

const updateClassSchema = z
  .object({
    lecturer_id: z.string().optional(),
    max_students: z.coerce.number().min(1, 'Sĩ số tối thiểu là 1').max(500, 'Sĩ số tối đa là 500'),
    late_after_min: z.coerce.number().min(0, 'Phút đi trễ không được âm'),
    absent_after_min: z.coerce.number().min(1, 'Phút tính vắng tối thiểu là 1'),
    weight_present: z.coerce.number().min(0).max(1),
    weight_late: z.coerce.number().min(0).max(1),
    weight_excused: z.coerce.number().min(0).max(1),
    attendance_warning_absences: z.coerce.number().min(1),
  })
  .refine((data) => data.late_after_min < data.absent_after_min, {
    message: 'Mốc đi trễ phải nhỏ hơn mốc tính vắng',
    path: ['absent_after_min'],
  })

type UpdateClassFormValues = z.infer<typeof updateClassSchema>

export const ClassDetailPage = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const classId = parseInt(id || '0', 10)

  const [classData, setClassData] = useState<Class | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [tabParams, setTabParams] = useSearchParams()
  const activeTab = tabParams.get('tab') || 'info'
  const setActiveTab = (tab: string) => setTabParams({ tab }, { replace: true })

  // Actions
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [activateConfirmOpen, setActivateConfirmOpen] = useState(false)
  const [closeConfirmOpen, setCloseConfirmOpen] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<UpdateClassFormValues>({
    resolver: zodResolver(updateClassSchema),
  })

  const fetchClassDetail = useCallback(async (showLoading = false) => {
    if (!Number.isSafeInteger(classId) || classId <= 0) { setLoadError('Mã lớp học phần không hợp lệ.'); setLoading(false); return }
    if (showLoading) { setLoading(true); setClassData(null) }
    setLoadError('')
    try {
      const data = await classesApi.getById(classId)
      setClassData(data)
    } catch (error: unknown) {
      const msg = getApiErrorMessage(error, 'Không thể tải thông tin lớp học.')
      setLoadError(msg)
      if (!showLoading) toast.error(msg)
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [classId])

  useEffect(() => {
    fetchClassDetail(true)
  }, [fetchClassDetail])

  const handleOpenEdit = () => {
    if (!classData) return
    reset({
      lecturer_id: classData.lecturer_id ? classData.lecturer_id.toString() : 'none',
      max_students: classData.max_students,
      late_after_min: classData.late_after_min,
      absent_after_min: classData.absent_after_min,
      weight_present: classData.weight_present,
      weight_late: classData.weight_late,
      weight_excused: classData.weight_excused,
      attendance_warning_absences: classData.attendance_warning_absences,
    })
    setIsEditModalOpen(true)
  }

  const handleUpdateSubmit = async (values: UpdateClassFormValues) => {
    if (!classData) return
    try {
      const payload: ClassUpdateDTO = {
        lecturer_id: values.lecturer_id && values.lecturer_id !== 'none' ? parseInt(values.lecturer_id, 10) : null,
        max_students: values.max_students,
        late_after_min: values.late_after_min,
        absent_after_min: values.absent_after_min,
        weight_present: values.weight_present,
        weight_late: values.weight_late,
        weight_excused: values.weight_excused,
        attendance_warning_absences: values.attendance_warning_absences,
      }
      await classesApi.update(classData.id, payload)
      toast.success('Cập nhật lớp học phần thành công')
      setIsEditModalOpen(false)
      fetchClassDetail()
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.detail?.message || (error as any)?.response?.data?.error?.message || 'Không thể cập nhật lớp học'
      toast.error(msg)
    }
  }

  const handleActivate = async () => {
    if (!classData) return
    setActionLoading(true)
    try {
      await classesApi.activate(classData.id)
      toast.success('Đã kích hoạt lớp học phần thành công')
      setActivateConfirmOpen(false)
      fetchClassDetail()
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.detail?.message || (error as any)?.response?.data?.error?.message || 'Không thể kích hoạt lớp học'
      toast.error(msg)
    } finally {
      setActionLoading(false)
    }
  }

  const handleClose = async () => {
    if (!classData) return
    setActionLoading(true)
    try {
      await classesApi.close(classData.id)
      toast.success('Đã đóng lớp học phần')
      setCloseConfirmOpen(false)
      fetchClassDetail()
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.detail?.message || (error as any)?.response?.data?.error?.message || 'Không thể đóng lớp học'
      toast.error(msg)
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!classData) {
    return (
      <div className="text-center py-16 space-y-4">
        <p role="alert">{loadError || 'Không thể tải thông tin lớp học phần.'}</p>
        <Button variant="outline" onClick={() => void fetchClassDetail(true)}>Thử lại</Button>
        <Button variant="outline" onClick={() => navigate('/admin/classes')}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Quay lại danh sách lớp
        </Button>
      </div>
    )
  }

  const isClosed = classData.status === 'closed'
  const isDraft = classData.status === 'draft'
  const isActive = classData.status === 'active'

  return (
    <div className="space-y-5">

      <ClassPageHeader
        code={classData.code}
        subjectName={classData.subject_name || classData.code}
        semesterName={classData.semester_name}
        lecturerName={classData.lecturer_name}
        status={classData.status}
        backHref="/admin/classes"
        backLabel="Lớp học phần"
        actions={
          !isClosed ? (
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleOpenEdit}>
                <Pencil className="mr-2 h-4 w-4" /> Chỉnh sửa thông tin
              </Button>

              {isDraft && (
                <Button size="sm" onClick={() => setActivateConfirmOpen(true)}>
                  <CheckCircle2 className="mr-2 h-4 w-4" /> Kích hoạt lớp
                </Button>
              )}

              {isActive && (
                <Button variant="secondary" size="sm" onClick={() => setCloseConfirmOpen(true)}>
                  <Lock className="mr-2 h-4 w-4" /> Đóng lớp học
                </Button>
              )}
            </div>
          ) : undefined
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="min-w-0 space-y-4 [&_[role=tabpanel]]:min-w-0">
        <ClassNavigation value={activeTab} onChange={setActiveTab} />

        {/* TAB 1: THÔNG TIN CHUNG */}
        <TabsContent value="info" className="space-y-4">
          <ClassOverview classData={classData} />
          {isDraft && <div className="rounded-lg border p-4 text-sm"><p className="font-medium">Chuẩn bị lớp học phần</p><p className="mt-1 text-muted-foreground">Phân công giảng viên và thiết lập ít nhất một lịch trước khi kích hoạt. Thêm sinh viên khi có danh sách.</p><div className="mt-3 flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={handleOpenEdit}>Phân công giảng viên</Button><Button variant="outline" size="sm" onClick={() => setActiveTab('schedules')}>Thiết lập lịch</Button><Button variant="outline" size="sm" onClick={() => setActiveTab('students')}>Quản lý sinh viên</Button></div></div>}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <BookOpen className="h-4 w-4 text-primary" /> Thông tin học phần
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="grid grid-cols-3 py-1.5 border-b">
                  <span className="text-muted-foreground">Mã lớp:</span>
                  <span className="col-span-2 font-semibold">{classData.code}</span>
                </div>
                <div className="grid grid-cols-3 py-1.5 border-b">
                  <span className="text-muted-foreground">Môn học:</span>
                  <span className="col-span-2 font-medium">
                    {classData.subject_name} ({classData.subject_code})
                  </span>
                </div>
                <div className="grid grid-cols-3 py-1.5 border-b">
                  <span className="text-muted-foreground">Học kỳ:</span>
                  <span className="col-span-2">{classData.semester_name}</span>
                </div>
                <div className="grid grid-cols-3 py-1.5 border-b">
                  <span className="text-muted-foreground">Giảng viên:</span>
                  <span className="col-span-2 font-medium">
                    {classData.lecturer_name ? (
                      `${classData.lecturer_name} (${classData.lecturer_code})`
                    ) : (
                      <span className="text-muted-foreground italic">Chưa phân công</span>
                    )}
                  </span>
                </div>
                <div className="grid grid-cols-3 py-1.5">
                  <span className="text-muted-foreground">Sĩ số:</span>
                  <span className="col-span-2">
                    <strong className="text-primary">{classData.enrolled_count}</strong> / {classData.max_students} sinh viên
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <SlidersHorizontal className="h-4 w-4 text-primary" /> Quy định chuyên cần & Điểm danh
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="grid grid-cols-3 py-1.5 border-b">
                  <span className="text-muted-foreground">Mốc đi trễ:</span>
                  <span className="col-span-2">{classData.late_after_min} phút sau khi bắt đầu</span>
                </div>
                <div className="grid grid-cols-3 py-1.5 border-b">
                  <span className="text-muted-foreground">Mốc tính vắng:</span>
                  <span className="col-span-2">{classData.absent_after_min} phút sau khi bắt đầu</span>
                </div>
                <div className="grid grid-cols-3 py-1.5 border-b">
                  <span className="text-muted-foreground">Trọng số:</span>
                  <span className="col-span-2">
                    Có mặt: {classData.weight_present} • Trễ: {classData.weight_late} • Phép: {classData.weight_excused}
                  </span>
                </div>
                <div className="grid grid-cols-3 py-1.5">
                  <span className="text-muted-foreground">Cảnh báo vắng:</span>
                  <span className="col-span-2">Khi vắng từ {classData.attendance_warning_absences} buổi</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* TAB 2: SINH VIÊN */}
        <TabsContent value="students">
          <Card>
            <CardContent className="p-5 sm:p-6">
              <ClassStudentsTab
                classData={classData}
                canManage={!isClosed}
                onClassUpdated={fetchClassDetail}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 3: LỊCH & BUỔI HỌC */}
        <TabsContent value="schedules">
          <Card>
            <CardContent className="p-5 sm:p-6">
              <ClassSchedulesTab
                classData={classData}
                canManage={!isClosed}
                onClassUpdated={fetchClassDetail}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="attendance">
          <AttendancePanel classId={classData.id} />
        </TabsContent>

        <TabsContent value="assignments">
          <AssignmentsPanel classId={classData.id} canManage={!isClosed} />
        </TabsContent>
        <TabsContent value="questions"><QuestionBankPanel subjectId={classData.subject_id} subjectName={classData.subject_name} /></TabsContent>
        <TabsContent value="grades"><GradebookPanel classId={classData.id} writable={!isClosed} /></TabsContent>
<TabsContent value="exams"><ExamDraftPanel classId={classData.id} subjectId={classData.subject_id} canManage={!isClosed} /></TabsContent>
        <TabsContent value="announcements">
          <AnnouncementsPanel classId={classData.id} canManage={!isClosed} />
        </TabsContent>
        <TabsContent value="groups">
          <GroupsPanel classId={classData.id} canManage={!isClosed} />
        </TabsContent>
      <TabsContent value="leave"><LeaveRequestsPanel writable={classData.status !== 'closed'} classId={classData.id} /></TabsContent>
        <TabsContent value="report"><AttendanceReportPanel classId={classData.id} /></TabsContent>
        <TabsContent value="materials"><MaterialsPanel classId={classData.id} canManage={!isClosed} /></TabsContent>
      </Tabs>

      <Dialog open={isEditModalOpen} onOpenChange={setIsEditModalOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <form onSubmit={handleSubmit(handleUpdateSubmit)}>
            <DialogHeader>
              <DialogTitle>Chỉnh sửa Lớp học phần {classData.code}</DialogTitle>
            </DialogHeader>

            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Giảng viên phụ trách</Label>
                <Controller
                  control={control}
                  name="lecturer_id"
                  render={({ field }) => (
                    <RemoteSearchSelect value={field.value || 'none'} onChange={field.onChange} label="Giảng viên phụ trách" emptyValue="none" emptyLabel="Chưa phân công" search={searchLecturers} selectedLabel={classData.lecturer_id && classData.lecturer_name ? `${classData.lecturer_name} (${classData.lecturer_code || ''})` : undefined} />
                  )}
                />
              </div>

              <div className="space-y-2">
                <Label>Sĩ số tối đa</Label>
                <Input type="number" min={1} max={500} {...register('max_students')} />
                {errors.max_students && <p className="text-xs text-destructive">{errors.max_students.message}</p>}
              </div>

              <div className="p-3 bg-muted/40 rounded-lg space-y-3 border text-xs">
                <div className="font-semibold text-foreground">Cài đặt điểm danh</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs">Tính trễ sau (phút)</Label>
                    <Input type="number" className="h-8 text-xs mt-1" {...register('late_after_min')} />
                    {errors.late_after_min && <p className="text-destructive text-[11px]">{errors.late_after_min.message}</p>}
                  </div>
                  <div>
                    <Label className="text-xs">Tính vắng sau (phút)</Label>
                    <Input type="number" className="h-8 text-xs mt-1" {...register('absent_after_min')} />
                    {errors.absent_after_min && <p className="text-destructive text-[11px]">{errors.absent_after_min.message}</p>}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <Label className="text-xs">Trọng số Có mặt</Label>
                    <Input type="number" step="0.1" className="h-8 text-xs mt-1" {...register('weight_present')} />
                  </div>
                  <div>
                    <Label className="text-xs">Trọng số Đi muộn</Label>
                    <Input type="number" step="0.1" className="h-8 text-xs mt-1" {...register('weight_late')} />
                  </div>
                  <div>
                    <Label className="text-xs">Trọng số Có phép</Label>
                    <Input type="number" step="0.1" className="h-8 text-xs mt-1" {...register('weight_excused')} />
                  </div>
                </div>

                <div>
                  <Label className="text-xs">Ngưỡng cảnh báo vắng (buổi)</Label>
                  <Input type="number" className="h-8 text-xs mt-1" {...register('attendance_warning_absences')} />
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsEditModalOpen(false)}>
                Hủy
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                Lưu thay đổi
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={activateConfirmOpen} onOpenChange={setActivateConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-success" />
              Kích hoạt lớp học phần
            </AlertDialogTitle>
            <AlertDialogDescription>
              Khi chuyển sang <strong>Đang hoạt động</strong>, lớp học phải có giảng viên phụ trách và ít nhất 1 lịch học hằng tuần. Bạn có muốn kích hoạt lớp <strong>{classData.code}</strong> không?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction onClick={handleActivate} disabled={actionLoading}>
              {actionLoading ? 'Đang kích hoạt...' : 'Kích hoạt ngay'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={closeConfirmOpen} onOpenChange={setCloseConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Lock className="h-5 w-5 text-destructive" />
              Xác nhận đóng lớp học phần
            </AlertDialogTitle>
            <AlertDialogDescription>
              Khi chuyển sang <strong>Đã đóng (Closed)</strong>, lớp học này sẽ trở thành <strong>chỉ đọc (Read-only)</strong> và không thể thêm sửa sinh viên hoặc lịch học nữa.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleClose}
              disabled={actionLoading}
            >
              {actionLoading ? 'Đang xử lý...' : 'Xác nhận đóng lớp'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default ClassDetailPage
