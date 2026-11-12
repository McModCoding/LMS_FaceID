import { useState, useEffect, useRef } from 'react'
import { PlusCircle, Pencil, Trash2, Search } from 'lucide-react'
import { toast } from 'sonner'
import { Controller, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'

import { Subject } from '../../types/subject'
import { subjectsApi } from '../../api/subjects'
import { departmentsApi } from '../../api/departments'
import { Department } from '../../types/department'

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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { QuestionBankPanel } from '@/components/classes/QuestionBankPanel'

const schema = z.object({
  code: z.string().min(1, 'Vui lòng nhập mã môn'),
  name: z.string().min(1, 'Vui lòng nhập tên môn'),
  credits: z.coerce.number().min(1, 'Số tín chỉ phải lớn hơn 0'),
  department_id: z.coerce.number().optional(),
})

type FormValues = z.infer<typeof schema>

export const SubjectsPage = () => {
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [loading, setLoading] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingSubject, setEditingSubject] = useState<Subject | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<Subject | null>(null)
  const [departments, setDepartments] = useState<Department[]>([])
  const [departmentFilter, setDepartmentFilter] = useState('all')
  const [questionSubject, setQuestionSubject] = useState<Subject | null>(null)

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handleSearchChange = (val: string) => {
    setSearchInput(val)
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(val)
    }, 300)
  }

  const fetchSubjects = async (query?: string) => {
    setLoading(true)
    try {
      const data = await subjectsApi.getAll(query, departmentFilter === 'all' ? undefined : departmentFilter === 'unassigned' ? 0 : Number(departmentFilter))
      setSubjects(data)
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.error?.message || 'Không thể tải danh sách môn học'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSubjects(debouncedSearch.trim() || undefined)
  }, [debouncedSearch, departmentFilter])

  useEffect(() => { void departmentsApi.getAll().then((items) => setDepartments(items.filter((item) => item.is_active))).catch(() => toast.error('Không thể tải danh sách khoa')) }, [])

  const handleOpenAddModal = () => {
    setEditingSubject(null)
    reset({ code: '', name: '', credits: 3, department_id: undefined })
    setIsModalOpen(true)
  }

  const handleOpenEditModal = (record: Subject) => {
    setEditingSubject(record)
    reset({
      code: record.code,
      name: record.name,
      credits: record.credits,
      department_id: record.department_id || undefined,
    })
    setIsModalOpen(true)
  }

  const onSubmit = async (values: FormValues) => {
    try {
      if (editingSubject) {
        await subjectsApi.update(editingSubject.id, values)
        toast.success('Cập nhật môn học thành công')
      } else {
        await subjectsApi.create(values)
        toast.success('Thêm môn học thành công')
      }
      setIsModalOpen(false)
      fetchSubjects(debouncedSearch.trim() || undefined)
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.error?.message || 'Có lỗi xảy ra'
      toast.error(msg)
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    try {
      await subjectsApi.delete(deleteConfirm.id)
      toast.success('Xóa môn học thành công')
      fetchSubjects(debouncedSearch.trim() || undefined)
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.error?.message || 'Không thể xóa môn học'
      toast.error(msg)
    } finally {
      setDeleteConfirm(null)
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-4 flex-wrap gap-4">
        <CardTitle>Quản lý Môn học</CardTitle>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Tìm kiếm mã, tên môn học..."
              className="pl-8"
              value={searchInput}
              onChange={(e) => handleSearchChange(e.target.value)}
            />
          </div>
          <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
            <SelectTrigger className="w-[190px]"><SelectValue placeholder="Tất cả khoa" /></SelectTrigger>
            <SelectContent><SelectItem value="all">Tất cả khoa</SelectItem><SelectItem value="unassigned">Chưa gán khoa</SelectItem>{departments.map((department) => <SelectItem key={department.id} value={String(department.id)}>{department.code} · {department.name}</SelectItem>)}</SelectContent>
          </Select>
          <Button onClick={handleOpenAddModal}>
            <PlusCircle className="mr-2 h-4 w-4" /> Thêm Môn học
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : subjects.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            {debouncedSearch ? 'Không tìm thấy môn học nào khớp với tìm kiếm.' : 'Chưa có môn học nào trong danh sách.'}
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16 text-center">STT</TableHead>
                  <TableHead>Mã môn</TableHead>
                  <TableHead>Tên môn học</TableHead>
                  <TableHead>Khoa</TableHead>
                  <TableHead className="text-center">Số tín chỉ</TableHead>
                  <TableHead className="text-right">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {subjects.map((s, idx) => (
                  <TableRow key={s.id}>
                    <TableCell className="text-center">{idx + 1}</TableCell>
                    <TableCell className="font-medium">{s.code}</TableCell>
                    <TableCell>{s.name}</TableCell>
                    <TableCell>{s.department_name || 'Chưa gán'}</TableCell>
                    <TableCell className="text-center">{s.credits}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => setQuestionSubject(s)}>
                          Câu hỏi
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenEditModal(s)}
                          title="Sửa"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setDeleteConfirm(s)}
                          title="Xóa"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <Dialog open={!!questionSubject} onOpenChange={open => { if (!open) setQuestionSubject(null) }}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle>Ngân hàng câu hỏi</DialogTitle></DialogHeader>
            {questionSubject && <QuestionBankPanel subjectId={questionSubject.id} subjectName={questionSubject.name} />}
          </DialogContent>
        </Dialog>
        <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
          <DialogContent>
            <form onSubmit={handleSubmit(onSubmit)}>
              <DialogHeader>
                <DialogTitle>{editingSubject ? 'Chỉnh sửa Môn học' : 'Thêm Môn học mới'}</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Mã môn học</Label>
                  <Input placeholder="Ví dụ: IT101" disabled={!!editingSubject} {...register('code')} />
                  {errors.code && <p className="text-xs text-destructive">{errors.code.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Tên môn học</Label>
                  <Input placeholder="Ví dụ: Nhập môn Lập trình" {...register('name')} />
                  {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Số tín chỉ</Label>
                  <Input type="number" min={1} max={10} {...register('credits')} />
                  {errors.credits && <p className="text-xs text-destructive">{errors.credits.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Khoa</Label>
                  <Controller control={control} name="department_id" render={({ field }) => <Select value={field.value ? String(field.value) : 'none'} onValueChange={(value) => field.onChange(value === 'none' ? undefined : Number(value))}><SelectTrigger><SelectValue placeholder="Chọn khoa" /></SelectTrigger><SelectContent><SelectItem value="none">Chưa gán khoa</SelectItem>{departments.map((department) => <SelectItem key={department.id} value={String(department.id)}>{department.code} · {department.name}</SelectItem>)}</SelectContent></Select>} />
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
                  Hủy
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {editingSubject ? 'Lưu thay đổi' : 'Thêm mới'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        <AlertDialog open={!!deleteConfirm} onOpenChange={(o) => !o && setDeleteConfirm(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Xác nhận xóa</AlertDialogTitle>
              <AlertDialogDescription>
                Bạn có chắc chắn muốn xóa môn học <strong>{deleteConfirm?.name}</strong> không?
                Hành động này không thể hoàn tác.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Hủy</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={handleDelete}
              >
                Xóa
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  )
}

export default SubjectsPage
