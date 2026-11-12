import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlusCircle, Pencil, Trash2, Search, Lock, Unlock, KeyRound, Eye } from 'lucide-react'
import { toast } from 'sonner'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'

import { Lecturer, LecturerType } from '../../types/lecturer'
import { lecturersApi } from '../../api/lecturers'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { getApiErrorMessage } from '@/lib/api-error'

const lecturerSchema = z.object({
  code: z.string().min(1, 'Vui lòng nhập mã giảng viên'),
  full_name: z.string().min(1, 'Vui lòng nhập họ và tên'),
  email: z.string().email('Email không hợp lệ').min(1, 'Vui lòng nhập email'),
  phone: z.string().optional(),
  degree: z.string().optional(),
  type: z.enum(['full_time', 'visiting']).default('full_time'),
  department_id: z.coerce.number().optional(),
})

type FormValues = z.infer<typeof lecturerSchema>

export const LecturersPage = () => {
  const navigate = useNavigate()
  const [lecturers, setLecturers] = useState<Lecturer[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const pageSize = 10
  const [total, setTotal] = useState(0)

  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<LecturerType | 'all'>('all')
  const [departmentFilter, setDepartmentFilter] = useState('all')
  const [departments, setDepartments] = useState<Department[]>([])

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingLecturer, setEditingLecturer] = useState<Lecturer | null>(null)

  const [deleteConfirm, setDeleteConfirm] = useState<Lecturer | null>(null)
  const [statusConfirm, setStatusConfirm] = useState<Lecturer | null>(null)
  const [resetPwConfirm, setResetPwConfirm] = useState<Lecturer | null>(null)

  const [tempPasswordModal, setTempPasswordModal] = useState<TemporaryPasswordState>({
    visible: false,
    password: '',
    title: '',
  })

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(lecturerSchema),
    defaultValues: { type: 'full_time' },
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

  const handleTypeChange = (val: string) => {
    setTypeFilter(val as LecturerType | 'all')
    setPage(1)
  }

  useEffect(() => { void departmentsApi.getAll().then((items) => setDepartments(items.filter((item) => item.is_active))).catch(() => toast.error('Không thể tải danh sách khoa')) }, [])

  const fetchLecturers = useCallback(async () => {
    setLoading(true)
    try {
      const res = await lecturersApi.getAll({
        page,
        page_size: pageSize,
        q: debouncedSearch.trim() || undefined,
        type: typeFilter !== 'all' ? typeFilter : undefined,
        department_id: departmentFilter === 'all' ? undefined : departmentFilter === 'unassigned' ? 0 : Number(departmentFilter),
      })
      setLecturers(res.items)
      setTotal(res.total)
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, 'Không thể tải danh sách giảng viên'))
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, debouncedSearch, typeFilter, departmentFilter])

  useEffect(() => {
    fetchLecturers()
  }, [fetchLecturers])

  const handleOpenAddModal = () => {
    setEditingLecturer(null)
    reset({ code: '', full_name: '', email: '', phone: '', degree: '', department_id: undefined, type: 'full_time' })
    setIsModalOpen(true)
  }

  const handleOpenEditModal = (record: Lecturer) => {
    setEditingLecturer(record)
    reset({
      code: record.code,
      full_name: record.full_name,
      email: record.email || '',
      phone: record.phone || '',
      degree: record.degree || '',
      department_id: record.department_id || undefined,
      type: record.type,
    })
    setIsModalOpen(true)
  }

  const onSubmit = async (values: FormValues) => {
    try {
      if (editingLecturer) {
        await lecturersApi.update(editingLecturer.id, values)
        toast.success('Cập nhật giảng viên thành công')
        setIsModalOpen(false)
        fetchLecturers()
      } else {
        const res = await lecturersApi.create(values)
        toast.success('Thêm giảng viên thành công')
        setIsModalOpen(false)
        fetchLecturers()
        if (res.temp_password) {
          setTempPasswordModal({
            visible: true,
            password: res.temp_password,
            title: `Mật khẩu tạm thời cho giảng viên ${res.lecturer.full_name}`,
          })
        }
      }
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, 'Có lỗi xảy ra'))
    }
  }

  const handleToggleStatus = async () => {
    if (!statusConfirm || typeof statusConfirm.user_is_active !== 'boolean') return
    try {
      const currentActive = statusConfirm.user_is_active
      await usersApi.toggleStatus(statusConfirm.user_id, !currentActive)
      toast.success(currentActive ? 'Khóa tài khoản thành công' : 'Mở khóa tài khoản thành công')
      fetchLecturers()
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
        title: `Mật khẩu mới cho giảng viên ${resetPwConfirm.full_name}`,
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
      await lecturersApi.delete(deleteConfirm.id)
      toast.success('Xóa giảng viên thành công')
      fetchLecturers()
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, 'Không thể xóa giảng viên'))
    } finally {
      setDeleteConfirm(null)
    }
  }

  return (
    <TooltipProvider>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-4 flex-wrap gap-4">
          <CardTitle>Quản lý Giảng viên</CardTitle>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative w-64">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Tìm kiếm mã, tên, email..."
                className="pl-8"
                value={searchInput}
                onChange={(e) => handleSearchChange(e.target.value)}
              />
            </div>
            <Select value={typeFilter} onValueChange={handleTypeChange}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Tất cả loại giảng viên" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tất cả loại giảng viên</SelectItem>
                <SelectItem value="full_time">Cơ hữu</SelectItem>
                <SelectItem value="visiting">Thỉnh giảng</SelectItem>
              </SelectContent>
            </Select>
            <Select value={departmentFilter} onValueChange={(value) => { setDepartmentFilter(value); setPage(1) }}>
              <SelectTrigger className="w-[200px]"><SelectValue placeholder="Tất cả khoa" /></SelectTrigger>
              <SelectContent><SelectItem value="all">Tất cả khoa</SelectItem><SelectItem value="unassigned">Chưa gán khoa</SelectItem>{departments.map((department) => <SelectItem key={department.id} value={String(department.id)}>{department.code} · {department.name}</SelectItem>)}</SelectContent>
            </Select>
            <Button onClick={handleOpenAddModal}>
              <PlusCircle className="mr-2 h-4 w-4" /> Thêm Giảng viên
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
          ) : lecturers.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {debouncedSearch || typeFilter !== 'all'
                ? 'Không tìm thấy giảng viên nào khớp với điều kiện tìm kiếm/lọc'
                : 'Chưa có giảng viên nào trong danh sách'}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Mã GV</TableHead>
                    <TableHead>Họ và tên</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>SĐT</TableHead>
                    <TableHead>Học vị</TableHead>
                    <TableHead>Khoa</TableHead>
                    <TableHead>Loại giảng viên</TableHead>
                    <TableHead>Tài khoản</TableHead>
                    <TableHead className="text-right">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {lecturers.map((l) => (
                    <TableRow key={l.id}>
                      <TableCell className="font-medium">{l.code}</TableCell>
                      <TableCell>{l.full_name}</TableCell>
                      <TableCell>{l.email || '-'}</TableCell>
                      <TableCell>{l.phone || '-'}</TableCell>
                      <TableCell>{l.degree || '-'}</TableCell>
                      <TableCell>{l.department_name || l.department || 'Chưa gán khoa'}</TableCell>
                      <TableCell>
                        {l.type === 'full_time' ? (
                          <Badge variant="outline" className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                            Cơ hữu
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                            Thỉnh giảng
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {l.user_is_active === true ? (
                          <Badge variant="success">Hoạt động</Badge>
                        ) : l.user_is_active === false ? (
                          <Badge variant="destructive">Đã khóa</Badge>
                        ) : (
                          <Badge variant="secondary">Chưa có thông tin</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="ghost" size="icon" onClick={() => navigate(`/admin/lecturers/${l.id}`)}>
                                <Eye className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Xem hồ sơ</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="ghost" size="icon" onClick={() => handleOpenEditModal(l)}>
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
                                className={l.user_is_active ? 'text-destructive hover:text-destructive' : 'text-success hover:text-success'}
                                disabled={typeof l.user_is_active !== 'boolean'}
                                onClick={() => setStatusConfirm(l)}
                              >
                                {l.user_is_active ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4" />}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              {typeof l.user_is_active !== 'boolean' ? 'Chưa có trạng thái tài khoản' : l.user_is_active ? 'Khóa tài khoản' : 'Mở khóa tài khoản'}
                            </TooltipContent>
                          </Tooltip>

                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="ghost" size="icon" onClick={() => setResetPwConfirm(l)}>
                                <KeyRound className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Reset mật khẩu</TooltipContent>
                          </Tooltip>

                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" onClick={() => setDeleteConfirm(l)}>
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
                Tổng số: {total} giảng viên
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
                  <DialogTitle>{editingLecturer ? 'Chỉnh sửa Giảng viên' : 'Thêm Giảng viên mới'}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label>Mã giảng viên</Label>
                    <Input placeholder="Ví dụ: GV001" disabled={!!editingLecturer} {...register('code')} />
                    {errors.code && <p className="text-xs text-destructive">{errors.code.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label>Họ và tên</Label>
                    <Input placeholder="Ví dụ: Nguyễn Văn A" {...register('full_name')} />
                    {errors.full_name && <p className="text-xs text-destructive">{errors.full_name.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label>Email</Label>
                    <Input placeholder="Ví dụ: nva@university.edu.vn" {...register('email')} />
                    {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label>Số điện thoại</Label>
                    <Input placeholder="Ví dụ: 0901234567" {...register('phone')} />
                  </div>
                  <div className="space-y-2">
                    <Label>Học vị/Học hàm</Label>
                    <Input placeholder="Ví dụ: Tiến sĩ, Thạc sĩ, PGS.TS" {...register('degree')} />
                  </div>
                  <div className="space-y-2">
                    <Label>Loại giảng viên</Label>
                    <Controller
                      control={control}
                      name="type"
                      render={({ field: { value, onChange } }) => (
                        <Select value={value} onValueChange={onChange}>
                          <SelectTrigger>
                            <SelectValue placeholder="Chọn loại giảng viên" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="full_time">Cơ hữu</SelectItem>
                            <SelectItem value="visiting">Thỉnh giảng</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                    {errors.type && <p className="text-xs text-destructive">{errors.type.message}</p>}
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
                    {editingLecturer ? 'Lưu thay đổi' : 'Thêm mới'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>

          <TemporaryPasswordDialog
            state={tempPasswordModal}
            onClose={() => setTempPasswordModal((current) => ({ ...current, visible: false }))}
          />
          <AccountActionDialogs
            entityLabel="giảng viên"
            deleteTarget={deleteConfirm}
            statusTarget={
              statusConfirm && typeof statusConfirm.user_is_active === 'boolean'
                ? { full_name: statusConfirm.full_name, isActive: statusConfirm.user_is_active }
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

export default LecturersPage
