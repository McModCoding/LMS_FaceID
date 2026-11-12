import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  PlusCircle,
  Search,
  BookOpen,
  Trash2,
  Eye,
  SlidersHorizontal,
} from 'lucide-react'
import dayjs from 'dayjs'
import { toast } from 'sonner'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'

import { Class, ClassCreateDTO, ClassStatus } from '../../../types/class'
import { Semester } from '../../../types/semester'
import { Subject } from '../../../types/subject'
import { classesApi } from '../../../api/classes'
import { semestersApi } from '../../../api/semesters'
import { subjectsApi } from '../../../api/subjects'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { ClassStatusBadge } from '@/components/common/status-badge'
import { getApiErrorMessage } from '@/lib/api-error'
import { RemoteSearchSelect } from '@/components/common/RemoteSearchSelect'
import { searchLecturers } from '@/lib/admin-search-options'

const createClassSchema = z
  .object({
    code: z.string().min(1, 'Vui lòng nhập mã lớp học phần'),
    subject_id: z.string().min(1, 'Vui lòng chọn môn học'),
    semester_id: z.string().min(1, 'Vui lòng chọn học kỳ'),
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

type CreateClassFormValues = z.infer<typeof createClassSchema>

const findSemesterInProgress = (semesters: Semester[]) => {
  const today = dayjs().startOf('day')
  return semesters.find((semester) => {
    const startDate = dayjs(semester.start_date).startOf('day')
    const endDate = dayjs(semester.end_date).endOf('day')
    return !today.isBefore(startDate) && !today.isAfter(endDate)
  })
}

export const ClassesPage = () => {
  const navigate = useNavigate()
  const [classes, setClasses] = useState<Class[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [optionsError, setOptionsError] = useState('')
  const [optionsRetry, setOptionsRetry] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 10
  const [total, setTotal] = useState(0)

  // Filters
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedSemester, setSelectedSemester] = useState<string>('all')
  const [selectedSubject, setSelectedSubject] = useState<string>('all')
  const [selectedLecturer, setSelectedLecturer] = useState<string>('all')
  const [selectedStatus, setSelectedStatus] = useState<string>('all')

  // Options for filters & form
  const [semesters, setSemesters] = useState<Semester[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])

  // Modal create
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false)

  // Delete confirm
  const [deleteConfirmClass, setDeleteConfirmClass] = useState<Class | null>(null)

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateClassFormValues>({
    resolver: zodResolver(createClassSchema),
    defaultValues: {
      max_students: 50,
      late_after_min: 10,
      absent_after_min: 30,
      weight_present: 1.0,
      weight_late: 0.5,
      weight_excused: 1.0,
      attendance_warning_absences: 3,
    },
  })

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hasSelectedSemester = useRef(false)
  const requestId = useRef(0)
  const handleSearchChange = (val: string) => {
    setSearch(val)
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(val)
      setPage(1)
    }, 300)
  }

  // Fetch filter options
  useEffect(() => {
    let active = true
    const fetchOptions = async () => {
        setOptionsError('')
        const [semRes, subRes] = await Promise.allSettled([
          semestersApi.getAll(),
          subjectsApi.getAll(),
        ])
        if (!active) return
        if (semRes.status === 'fulfilled') setSemesters(semRes.value)
        if (subRes.status === 'fulfilled') setSubjects(subRes.value)

        // Default to the semester whose date range contains today; the filter remains editable.
        const semesterInProgress = semRes.status === 'fulfilled' ? findSemesterInProgress(semRes.value) : undefined
        if (semesterInProgress && !hasSelectedSemester.current) {
          setSelectedSemester(semesterInProgress.id.toString())
        }
        const failure = [semRes, subRes].find((result) => result.status === 'rejected')
        if (failure?.status === 'rejected') setOptionsError(getApiErrorMessage(failure.reason, 'Không thể tải đầy đủ bộ lọc.'))
    }
    void fetchOptions()
    return () => { active = false }
  }, [optionsRetry])

  // Fetch classes list
  const fetchClasses = useCallback(async () => {
    const currentRequest = ++requestId.current
    setLoading(true)
    setLoadError('')
    try {
      const res = await classesApi.getAll({
        page,
        page_size: pageSize,
        q: debouncedSearch.trim() || undefined,
        semester_id: selectedSemester !== 'all' ? parseInt(selectedSemester, 10) : undefined,
        subject_id: selectedSubject !== 'all' ? parseInt(selectedSubject, 10) : undefined,
        lecturer_id: selectedLecturer !== 'all' ? parseInt(selectedLecturer, 10) : undefined,
        status: selectedStatus !== 'all' ? (selectedStatus as ClassStatus) : undefined,
      })
      if (currentRequest === requestId.current) {
        setClasses(res.items)
        setTotal(res.total)
      }
    } catch (error: unknown) {
      if (currentRequest === requestId.current) setLoadError(getApiErrorMessage(error, 'Không thể tải danh sách lớp học.'))
    } finally {
      if (currentRequest === requestId.current) setLoading(false)
    }
  }, [page, pageSize, debouncedSearch, selectedSemester, selectedSubject, selectedLecturer, selectedStatus])

  useEffect(() => {
    void fetchClasses()
    return () => { requestId.current += 1 }
  }, [fetchClasses])

  const handleOpenCreateModal = () => {
    const semesterInProgress = findSemesterInProgress(semesters)
    reset({
      code: '',
      subject_id: '',
      semester_id: semesterInProgress?.id?.toString() || semesters[0]?.id?.toString() || '',
      lecturer_id: undefined,
      max_students: 50,
      late_after_min: 10,
      absent_after_min: 30,
      weight_present: 1.0,
      weight_late: 0.5,
      weight_excused: 1.0,
      attendance_warning_absences: 3,
    })
    setShowAdvancedSettings(false)
    setIsCreateModalOpen(true)
  }

  const handleCreateSubmit = async (values: CreateClassFormValues) => {
    try {
      const payload: ClassCreateDTO = {
        code: values.code.trim().toUpperCase(),
        subject_id: parseInt(values.subject_id, 10),
        semester_id: parseInt(values.semester_id, 10),
        lecturer_id: values.lecturer_id && values.lecturer_id !== 'none' ? parseInt(values.lecturer_id, 10) : null,
        max_students: values.max_students,
        late_after_min: values.late_after_min,
        absent_after_min: values.absent_after_min,
        weight_present: values.weight_present,
        weight_late: values.weight_late,
        weight_excused: values.weight_excused,
        attendance_warning_absences: values.attendance_warning_absences,
      }
      const created = await classesApi.create(payload)
      toast.success(`Đã tạo lớp học phần ${created.code} thành công`)
      setIsCreateModalOpen(false)
      fetchClasses()
      navigate(`/admin/classes/${created.id}`)
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.detail?.message || (error as any)?.response?.data?.error?.message || 'Tạo lớp học phần thất bại'
      toast.error(msg)
    }
  }

  const handleDeleteClass = async () => {
    if (!deleteConfirmClass) return
    try {
      await classesApi.delete(deleteConfirmClass.id)
      toast.success(`Đã xóa lớp ${deleteConfirmClass.code}`)
      setDeleteConfirmClass(null)
      fetchClasses()
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.detail?.message || (error as any)?.response?.data?.error?.message || 'Không thể xóa lớp học phần'
      toast.error(msg)
    }
  }

  return (
    <TooltipProvider>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-4 flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-primary" />
            <CardTitle>Quản lý Lớp học phần</CardTitle>
          </div>
          <Button onClick={handleOpenCreateModal}>
            <PlusCircle className="mr-2 h-4 w-4" /> Tạo Lớp mới
          </Button>
        </CardHeader>

        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">Lớp học phần là một lớp của môn học trong học kỳ. Mở chi tiết lớp để phân công giảng viên, thiết lập lịch và quản lý sinh viên.</p>
          {optionsError && <div role="alert" className="rounded-md border p-3 text-sm"><p>Không tải đủ dữ liệu bộ lọc: {optionsError}</p><Button variant="outline" size="sm" className="mt-2" onClick={() => setOptionsRetry((value) => value + 1)}>Thử tải lại bộ lọc</Button></div>}

          <div className="flex flex-wrap items-center gap-2.5 bg-muted/30 p-3 rounded-lg border">
            <div className="relative w-56">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Tìm mã lớp, tên môn..."
                className="pl-8"
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
              />
            </div>

            <Select
              value={selectedSemester}
              onValueChange={(val) => {
                hasSelectedSemester.current = true
                setSelectedSemester(val)
                setPage(1)
              }}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Chọn học kỳ" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tất cả học kỳ</SelectItem>
                {semesters.map((s) => (
                  <SelectItem key={s.id} value={s.id.toString()}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={selectedSubject}
              onValueChange={(val) => {
                setSelectedSubject(val)
                setPage(1)
              }}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Chọn môn học" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tất cả môn học</SelectItem>
                {subjects.map((sub) => (
                  <SelectItem key={sub.id} value={sub.id.toString()}>
                    {sub.code} - {sub.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="w-full sm:w-[220px]"><RemoteSearchSelect value={selectedLecturer} onChange={(val) => { setSelectedLecturer(val); setPage(1) }} label="Giảng viên" emptyValue="all" emptyLabel="Tất cả giảng viên" search={searchLecturers} /></div>

            <Select
              value={selectedStatus}
              onValueChange={(val) => {
                setSelectedStatus(val)
                setPage(1)
              }}
            >
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Trạng thái" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tất cả trạng thái</SelectItem>
                <SelectItem value="draft">Nháp</SelectItem>
                <SelectItem value="active">Đang hoạt động</SelectItem>
                <SelectItem value="closed">Đã đóng</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : loadError ? (
            <div role="alert" className="rounded-lg border p-6 text-center"><p>Không thể tải danh sách lớp học phần: {loadError}</p><Button variant="outline" className="mt-3" onClick={() => void fetchClasses()}>Thử lại</Button></div>
          ) : classes.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground border rounded-lg bg-card">
              Không có lớp học phần phù hợp. Hãy kiểm tra bộ lọc hoặc tạo lớp mới nếu cần.
            </div>
          ) : (
            <div className="rounded-md border bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16 text-center">STT</TableHead>
                    <TableHead>Mã lớp</TableHead>
                    <TableHead>Môn học</TableHead>
                    <TableHead>Học kỳ</TableHead>
                    <TableHead>Giảng viên</TableHead>
                    <TableHead className="text-center">Sĩ số</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead className="text-right">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {classes.map((c, idx) => (
                    <TableRow key={c.id}>
                      <TableCell className="text-center">{(page - 1) * pageSize + idx + 1}</TableCell>
                      <TableCell className="font-bold text-primary">{c.code}</TableCell>
                      <TableCell>
                        <div className="font-medium">{c.subject_name}</div>
                        <div className="text-xs text-muted-foreground">{c.subject_code}</div>
                      </TableCell>
                      <TableCell>{c.semester_name}</TableCell>
                      <TableCell>{c.lecturer_name || <span className="text-muted-foreground italic">Chưa phân công</span>}</TableCell>
                      <TableCell className="text-center">
                        <span className="font-semibold">{c.enrolled_count}</span>
                        <span className="text-muted-foreground text-xs"> / {c.max_students}</span>
                      </TableCell>
                      <TableCell><ClassStatusBadge status={c.status} /></TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => navigate(`/admin/classes/${c.id}`)}
                              >
                                <Eye className="h-4 w-4 mr-1" /> Chi tiết
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Xem chi tiết & Quản lý</TooltipContent>
                          </Tooltip>

                          {c.status === 'draft' && c.enrolled_count === 0 && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-destructive hover:text-destructive"
                                  onClick={() => setDeleteConfirmClass(c)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Xóa lớp nháp</TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {!loading && !loadError && total > 0 && (
            <div className="flex items-center justify-between px-2 py-2">
              <div className="text-sm text-muted-foreground">Tổng cộng: {total} lớp học phần</div>
              <div className="flex items-center space-x-2">
                <Button variant="outline" size="sm" onClick={() => setPage(page - 1)} disabled={page === 1}>
                  Trước
                </Button>
                <div className="text-sm font-medium">
                  Trang {page} / {Math.ceil(total / pageSize) || 1}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page + 1)}
                  disabled={page >= Math.ceil(total / pageSize)}
                >
                  Sau
                </Button>
              </div>
            </div>
          )}
        </CardContent>

        <Dialog open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen}>
          <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
            <form onSubmit={handleSubmit(handleCreateSubmit)}>
              <DialogHeader>
                <DialogTitle>Tạo Lớp học phần mới</DialogTitle>
              </DialogHeader>

              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Mã lớp học phần (duy nhất)</Label>
                  <Input placeholder="Ví dụ: IT101.01, CS202.N02" {...register('code')} />
                  {errors.code && <p className="text-xs text-destructive">{errors.code.message}</p>}
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Môn học</Label>
                    <Controller
                      control={control}
                      name="subject_id"
                      render={({ field }) => (
                        <Select value={field.value} onValueChange={field.onChange}>
                          <SelectTrigger>
                            <SelectValue placeholder="Chọn môn học" />
                          </SelectTrigger>
                          <SelectContent>
                            {subjects.map((sub) => (
                              <SelectItem key={sub.id} value={sub.id.toString()}>
                                {sub.code} - {sub.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                    {errors.subject_id && <p className="text-xs text-destructive">{errors.subject_id.message}</p>}
                  </div>

                  <div className="space-y-2">
                    <Label>Học kỳ</Label>
                    <Controller
                      control={control}
                      name="semester_id"
                      render={({ field }) => (
                        <Select value={field.value} onValueChange={field.onChange}>
                          <SelectTrigger>
                            <SelectValue placeholder="Chọn học kỳ" />
                          </SelectTrigger>
                          <SelectContent>
                            {semesters.map((s) => (
                              <SelectItem key={s.id} value={s.id.toString()}>
                                {s.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                    {errors.semester_id && <p className="text-xs text-destructive">{errors.semester_id.message}</p>}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Giảng viên phụ trách</Label>
                    <Controller
                      control={control}
                      name="lecturer_id"
                      render={({ field }) => (
                        <RemoteSearchSelect value={field.value || 'none'} onChange={field.onChange} label="Giảng viên phụ trách" emptyValue="none" emptyLabel="Chưa phân công" search={searchLecturers} />
                      )}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Sĩ số tối đa</Label>
                    <Input type="number" min={1} max={500} {...register('max_students')} />
                    {errors.max_students && <p className="text-xs text-destructive">{errors.max_students.message}</p>}
                  </div>
                </div>

                <div className="pt-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-xs text-muted-foreground hover:text-foreground"
                    onClick={() => setShowAdvancedSettings(!showAdvancedSettings)}
                  >
                    <SlidersHorizontal className="h-3.5 w-3.5 mr-1.5" />
                    {showAdvancedSettings ? 'Ẩn cài đặt điểm danh nâng cao' : 'Tùy chỉnh cài đặt điểm danh mặc định'}
                  </Button>
                </div>

                {showAdvancedSettings && (
                  <div className="p-3 bg-muted/40 rounded-lg space-y-3 border text-xs">
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
                )}
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsCreateModalOpen(false)}>
                  Hủy
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  Tạo lớp học
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        <AlertDialog open={!!deleteConfirmClass} onOpenChange={(o) => !o && setDeleteConfirmClass(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Xác nhận xóa lớp học phần</AlertDialogTitle>
              <AlertDialogDescription>
                Bạn có chắc chắn muốn xóa lớp <strong>{deleteConfirmClass?.code}</strong> không?
                Lưu ý: Chỉ có thể xóa lớp ở trạng thái Nháp chưa có sinh viên và buổi học.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Hủy</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={handleDeleteClass}
              >
                Xóa lớp
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </Card>
    </TooltipProvider>
  )
}

export default ClassesPage
