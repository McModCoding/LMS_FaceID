import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  PlusCircle,
  Pencil,
  Trash2,
  Search,
  Lock,
  Unlock,
  KeyRound,
  Upload,
  Download,
  Eye,
} from 'lucide-react'
import dayjs from 'dayjs'
import { toast } from 'sonner'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'

import { Student, StudentStatus } from '../../types/student'
import { studentsApi } from '../../api/students'
import { usersApi } from '../../api/users'
import { departmentsApi } from '../../api/departments'
import { Department } from '../../types/department'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
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
  AccountActionDialogs,
  TemporaryPasswordDialog,
  TemporaryPasswordState,
} from '@/components/admin/AdminAccountDialogs'
import { StudentImportDialog } from '@/components/admin/students/StudentImportDialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { getApiErrorMessage } from '@/lib/api-error'
import { downloadBlob } from '@/lib/download'

const studentSchema = z.object({
  student_code: z.string().min(1, 'Vui lòng nhập mã sinh viên'),
  full_name: z.string().min(1, 'Vui lòng nhập họ và tên'),
  admin_class: z.string().optional(),
  email: z.string().email('Email không hợp lệ').min(1, 'Vui lòng nhập email'),
  phone: z.string().optional(),
  gender: z.enum(['male', 'female', 'other']).optional(),
  dob: z.string().optional(),
  status: z.enum(['studying', 'suspended', 'graduated']).default('studying'),
  department_id: z.coerce.number().optional(),
})

type FormValues = z.infer<typeof studentSchema>

export const StudentsPage = () => {
  const navigate = useNavigate()
  const [students, setStudents] = useState<Student[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const pageSize = 10
  const [total, setTotal] = useState(0)

  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StudentStatus | 'all'>('all')
  const [departmentFilter, setDepartmentFilter] = useState('all')
  const [departments, setDepartments] = useState<Department[]>([])

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingStudent, setEditingStudent] = useState<Student | null>(null)

  const [deleteConfirm, setDeleteConfirm] = useState<Student | null>(null)
  const [statusConfirm, setStatusConfirm] = useState<Student | null>(null)
  const [resetPwConfirm, setResetPwConfirm] = useState<Student | null>(null)

  const [tempPasswordModal, setTempPasswordModal] = useState<TemporaryPasswordState>({
    visible: false,
    password: '',
    title: '',
  })

  const [isImportModalOpen, setIsImportModalOpen] = useState(false)

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(studentSchema),
    defaultValues: { status: 'studying' },
  })

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handleSearchChange = (val: string) => {
    setSearchInput(val)
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(val)
      setPage(1)
    }, 300)
  }

  const handleStatusChange = (val: string) => {
    setStatusFilter(val as StudentStatus | 'all')
    setPage(1)
  }

  useEffect(() => { void departmentsApi.getAll().then((items) => setDepartments(items.filter((item) => item.is_active))).catch(() => toast.error('Không thể tải danh sách khoa')) }, [])

  const fetchStudents = useCallback(async () => {
    setLoading(true)
    try {
      const res = await studentsApi.getAll({
        page,
        page_size: pageSize,
        search: debouncedSearch.trim() || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        department_id: departmentFilter === 'all' ? undefined : departmentFilter === 'unassigned' ? 0 : Number(departmentFilter),
      })
      setStudents(res.items)
      setTotal(res.total)
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, 'Không thể tải danh sách sinh viên'))
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, debouncedSearch, statusFilter, departmentFilter])

  useEffect(() => {
    fetchStudents()
  }, [fetchStudents])

  const handleOpenAddModal = () => {
    setEditingStudent(null)
    reset({
      student_code: '',
      full_name: '',
      admin_class: '',
      email: '',
      phone: '',
      status: 'studying',
      department_id: undefined,
      dob: '',
    })
    setIsModalOpen(true)
  }

  const handleOpenEditModal = (record: Student) => {
    setEditingStudent(record)
    reset({
      student_code: record.student_code,
      full_name: record.full_name,
      admin_class: record.admin_class || '',
      email: record.email || '',
      phone: record.phone || '',
      gender: (record.gender as any) || undefined,
      dob: record.dob || '',
      status: record.status,
      department_id: record.department_id || undefined,
    })
    setIsModalOpen(true)
  }

  const onSubmit = async (values: FormValues) => {
    try {
      const payload = {
        ...values,
        dob: values.dob || undefined,
      }
      if (editingStudent) {
        await studentsApi.update(editingStudent.id, payload)
        toast.success('Cập nhật sinh viên thành công')
        setIsModalOpen(false)
        fetchStudents()
      } else {
        const res = await studentsApi.create(payload)
        toast.success('Thêm sinh viên thành công')
        setIsModalOpen(false)
        fetchStudents()
        if (res.temp_password) {
          setTempPasswordModal({
            visible: true,
            password: res.temp_password,
            title: `Mật khẩu tạm thời cho sinh viên ${res.student.full_name}`,
          })
        }
      }
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, 'Có lỗi xảy ra'))
    }
  }

  const handleToggleStatus = async () => {
    if (!statusConfirm) return
    try {
      const currentActive = statusConfirm.user_is_active ?? true
      await usersApi.toggleStatus(statusConfirm.user_id, !currentActive)
      toast.success(currentActive ? 'Khóa tài khoản thành công' : 'Mở khóa tài khoản thành công')
      fetchStudents()
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, 'Không thể đổi trạng thái tài khoản'))
    } finally {
      setStatusConfirm(null)
    }
  }

  const handleResetPassword = async () => {
    if (!resetPwConfirm) return
    try {
      const res = await usersApi.resetPassword(resetPwConfirm.user_id)
      toast.success('Reset mật khẩu thành công')
      setTempPasswordModal({
        visible: true,
        password: res.temp_password,
        title: `Mật khẩu mới cho sinh viên ${resetPwConfirm.full_name}`,
      })
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, 'Không thể reset mật khẩu'))
    } finally {
      setResetPwConfirm(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    try {
      await studentsApi.delete(deleteConfirm.id)
      toast.success('Xóa sinh viên thành công')
      fetchStudents()
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, 'Không thể xóa sinh viên'))
    } finally {
      setDeleteConfirm(null)
    }
  }

  const handleExportExcel = async () => {
    try {
      toast.info('Đang xuất file Excel...')
      const blob = await studentsApi.exportExcel({
        search: debouncedSearch.trim() || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
      })
      downloadBlob(blob, `danh_sach_sinh_vien_${dayjs().format('YYYYMMDD')}.xlsx`)
      toast.success('Xuất Excel thành công!')
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, 'Không thể xuất file Excel'))
    }
  }

  return (
    <TooltipProvider>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-4 flex-wrap gap-4">
          <CardTitle>Quản lý Sinh viên</CardTitle>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative w-64">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Tìm kiếm mã, tên, lớp, email..."
                className="pl-8"
                value={searchInput}
                onChange={(e) => handleSearchChange(e.target.value)}
              />
            </div>
            <Select value={statusFilter} onValueChange={handleStatusChange}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Trạng thái" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tất cả trạng thái</SelectItem>
                <SelectItem value="studying">Đang học</SelectItem>
                <SelectItem value="suspended">Bảo lưu</SelectItem>
                <SelectItem value="graduated">Đã tốt nghiệp</SelectItem>
              </SelectContent>
            </Select>
          <Select value={departmentFilter} onValueChange={(value) => { setDepartmentFilter(value); setPage(1) }}>
            <SelectTrigger className="w-[190px]"><SelectValue placeholder="Tất cả khoa" /></SelectTrigger>
            <SelectContent><SelectItem value="all">Tất cả khoa</SelectItem><SelectItem value="unassigned">Chưa gán khoa</SelectItem>{departments.map((department) => <SelectItem key={department.id} value={String(department.id)}>{department.code} · {department.name}</SelectItem>)}</SelectContent>
          </Select>

            <Button variant="outline" onClick={() => setIsImportModalOpen(true)}>
              <Upload className="mr-2 h-4 w-4" /> Import Excel
            </Button>
            <Button variant="outline" onClick={handleExportExcel}>
              <Download className="mr-2 h-4 w-4" /> Xuất Excel
            </Button>
            <Button onClick={handleOpenAddModal}>
              <PlusCircle className="mr-2 h-4 w-4" /> Thêm Sinh viên
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : students.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {debouncedSearch || statusFilter !== 'all'
                ? 'Không tìm thấy sinh viên nào khớp với điều kiện tìm kiếm/lọc'
                : 'Chưa có sinh viên nào trong danh sách'}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Mã SV</TableHead>
                    <TableHead>Họ và tên</TableHead>
                    <TableHead>Lớp HC</TableHead>
                    <TableHead>Khoa</TableHead>
                    <TableHead>Ngày sinh</TableHead>
                    <TableHead>Giới tính</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>SĐT</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead>Tài khoản</TableHead>
                    <TableHead className="text-right">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {students.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell className="font-medium">{s.student_code}</TableCell>
                      <TableCell>{s.full_name}</TableCell>
                      <TableCell>{s.admin_class || '-'}</TableCell>
                      <TableCell>{s.department_name || 'Chưa gán'}</TableCell>
                      <TableCell>{s.dob ? dayjs(s.dob).format('DD/MM/YYYY') : '-'}</TableCell>
                      <TableCell>{s.gender || '-'}</TableCell>
                      <TableCell>{s.email || '-'}</TableCell>
                      <TableCell>{s.phone || '-'}</TableCell>
                      <TableCell>
                        {s.status === 'studying' && <Badge variant="success">Đang học</Badge>}
                        {s.status === 'suspended' && <Badge variant="warning">Bảo lưu</Badge>}
                        {s.status === 'graduated' && <Badge variant="secondary">Đã tốt nghiệp</Badge>}
                      </TableCell>
                      <TableCell>
                        {s.user_is_active !== false ? (
                          <Badge variant="success">Hoạt động</Badge>
                        ) : (
                          <Badge variant="destructive">Đã khóa</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="ghost" size="icon" onClick={() => navigate(`/admin/students/${s.id}`)}>
                                <Eye className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Xem hồ sơ</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="ghost" size="icon" onClick={() => handleOpenEditModal(s)}>
                                <Pencil className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Chỉnh sửa</TooltipContent>
                          </Tooltip>

                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className={s.user_is_active !== false ? 'text-destructive hover:text-destructive' : 'text-success hover:text-success'}
                                onClick={() => setStatusConfirm(s)}
                              >
                                {s.user_is_active !== false ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4" />}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              {s.user_is_active !== false ? 'Khóa tài khoản' : 'Mở khóa tài khoản'}
                            </TooltipContent>
                          </Tooltip>

                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="ghost" size="icon" onClick={() => setResetPwConfirm(s)}>
                                <KeyRound className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Reset mật khẩu</TooltipContent>
                          </Tooltip>

                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" onClick={() => setDeleteConfirm(s)}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Xóa</TooltipContent>
                          </Tooltip>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {total > 0 && (
            <div className="flex items-center justify-between px-2 py-4">
              <div className="text-sm text-muted-foreground">
                Tổng số: {total} sinh viên
              </div>
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                >
                  Trước
                </Button>
                <div className="text-sm font-medium">
                  Trang {page} / {Math.ceil(total / pageSize)}
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

          <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
            <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto">
              <form onSubmit={handleSubmit(onSubmit)}>
                <DialogHeader>
                  <DialogTitle>{editingStudent ? 'Chỉnh sửa Sinh viên' : 'Thêm Sinh viên mới'}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label>Mã sinh viên</Label>
                    <Input placeholder="Ví dụ: SV001" disabled={!!editingStudent} {...register('student_code')} />
                    {errors.student_code && <p className="text-xs text-destructive">{errors.student_code.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label>Họ và tên</Label>
                    <Input placeholder="Ví dụ: Nguyễn Văn B" {...register('full_name')} />
                    {errors.full_name && <p className="text-xs text-destructive">{errors.full_name.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label>Lớp hành chính</Label>
                    <Input placeholder="Ví dụ: K66-CNTT" {...register('admin_class')} />
                  </div>
                  <div className="space-y-2">
                    <Label>Email</Label>
                    <Input placeholder="Ví dụ: sv001@university.edu.vn" {...register('email')} />
                    {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label>Số điện thoại</Label>
                    <Input placeholder="Ví dụ: 0901234567" {...register('phone')} />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Giới tính</Label>
                      <Controller
                        control={control}
                        name="gender"
                        render={({ field: { value, onChange } }) => (
                          <Select value={value} onValueChange={onChange}>
                            <SelectTrigger>
                              <SelectValue placeholder="Chọn giới tính" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="male">Nam</SelectItem>
                              <SelectItem value="female">Nữ</SelectItem>
                              <SelectItem value="other">Khác</SelectItem>
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Ngày sinh</Label>
                      <Input type="date" {...register('dob')} />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Trạng thái học</Label>
                    <Controller
                      control={control}
                      name="status"
                      render={({ field: { value, onChange } }) => (
                        <Select value={value} onValueChange={onChange}>
                          <SelectTrigger>
                            <SelectValue placeholder="Chọn trạng thái" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="studying">Đang học</SelectItem>
                            <SelectItem value="suspended">Bảo lưu</SelectItem>
                            <SelectItem value="graduated">Đã tốt nghiệp</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Khoa</Label>
                  <Controller control={control} name="department_id" render={({ field }) => <Select value={field.value ? String(field.value) : 'none'} onValueChange={(value) => field.onChange(value === 'none' ? undefined : Number(value))}><SelectTrigger><SelectValue placeholder="Chọn khoa" /></SelectTrigger><SelectContent><SelectItem value="none">Chưa gán khoa</SelectItem>{departments.map((department) => <SelectItem key={department.id} value={String(department.id)}>{department.code} · {department.name}</SelectItem>)}</SelectContent></Select>} />
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
                    Hủy
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    {editingStudent ? 'Lưu thay đổi' : 'Thêm mới'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>

          <TemporaryPasswordDialog
            state={tempPasswordModal}
            onClose={() => setTempPasswordModal((current) => ({ ...current, visible: false }))}
          />

          <StudentImportDialog
            open={isImportModalOpen}
            onOpenChange={setIsImportModalOpen}
            onImported={fetchStudents}
          />

          <AccountActionDialogs
            entityLabel="sinh viên"
            deleteTarget={deleteConfirm}
            statusTarget={
              statusConfirm
                ? {
                    full_name: statusConfirm.full_name,
                    isActive: statusConfirm.user_is_active !== false,
                  }
                : null
            }
            resetPasswordTarget={resetPwConfirm}
            onCloseDelete={() => setDeleteConfirm(null)}
            onCloseStatus={() => setStatusConfirm(null)}
            onCloseResetPassword={() => setResetPwConfirm(null)}
            onDelete={handleDelete}
            onToggleStatus={handleToggleStatus}
            onResetPassword={handleResetPassword}
          />
        </CardContent>
      </Card>
    </TooltipProvider>
  )
}

export default StudentsPage
