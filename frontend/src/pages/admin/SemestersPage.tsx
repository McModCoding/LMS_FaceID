import { useState, useEffect } from 'react'
import { PlusCircle, Pencil, Trash2 } from 'lucide-react'
import dayjs from 'dayjs'
import { toast } from 'sonner'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'

import { Semester } from '../../types/semester'
import { semestersApi } from '../../api/semesters'

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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

const schema = z.object({
  name: z.string().min(1, 'Vui lòng nhập tên học kỳ'),
  start_date: z.string().min(1, 'Vui lòng chọn ngày bắt đầu'),
  end_date: z.string().min(1, 'Vui lòng chọn ngày kết thúc'),
})

type FormValues = z.infer<typeof schema>

const getSemesterStatus = (semester: Semester) => {
  const today = dayjs().startOf('day')
  const startDate = dayjs(semester.start_date).startOf('day')
  const endDate = dayjs(semester.end_date).endOf('day')

  if (today.isBefore(startDate)) return { label: 'Sắp diễn ra', variant: 'secondary' as const }
  if (today.isAfter(endDate)) return { label: 'Đã kết thúc', variant: 'outline' as const }
  return { label: 'Đang diễn ra', variant: 'success' as const }
}

export const SemestersPage = () => {
  const [semesters, setSemesters] = useState<Semester[]>([])
  const [loading, setLoading] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingSemester, setEditingSemester] = useState<Semester | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<Semester | null>(null)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', start_date: '', end_date: '' },
  })

  const fetchSemesters = async () => {
    setLoading(true)
    try {
      const data = await semestersApi.getAll()
      setSemesters(data)
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.error?.message || 'Không thể tải danh sách học kỳ'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSemesters()
  }, [])

  const handleOpenAddModal = () => {
    setEditingSemester(null)
    reset({ name: '', start_date: '', end_date: '' })
    setIsModalOpen(true)
  }

  const handleOpenEditModal = (record: Semester) => {
    setEditingSemester(record)
    reset({
      name: record.name,
      start_date: record.start_date,
      end_date: record.end_date,
    })
    setIsModalOpen(true)
  }

  const onSubmit = async (values: FormValues) => {
    try {
      if (editingSemester) {
        await semestersApi.update(editingSemester.id, values)
        toast.success('Cập nhật học kỳ thành công')
      } else {
        await semestersApi.create(values)
        toast.success('Thêm học kỳ thành công')
      }
      setIsModalOpen(false)
      fetchSemesters()
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.error?.message || 'Có lỗi xảy ra'
      toast.error(msg)
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    try {
      await semestersApi.delete(deleteConfirm.id)
      toast.success('Xóa học kỳ thành công')
      fetchSemesters()
    } catch (error: unknown) {
      const msg = (error as any)?.response?.data?.error?.message || 'Không thể xóa học kỳ'
      toast.error(msg)
    } finally {
      setDeleteConfirm(null)
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-4">
        <CardTitle>Quản lý Học kỳ</CardTitle>
        <Button onClick={handleOpenAddModal}>
          <PlusCircle className="mr-2 h-4 w-4" /> Thêm Học kỳ
        </Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : semesters.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">Chưa có học kỳ nào trong danh sách.</div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16 text-center">STT</TableHead>
                  <TableHead>Tên học kỳ</TableHead>
                  <TableHead>Ngày bắt đầu</TableHead>
                  <TableHead>Ngày kết thúc</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead className="text-right">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {semesters.map((s, idx) => {
                  const semesterStatus = getSemesterStatus(s)
                  return (
                  <TableRow key={s.id}>
                    <TableCell className="text-center">{idx + 1}</TableCell>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell>{dayjs(s.start_date).format('DD/MM/YYYY')}</TableCell>
                    <TableCell>{dayjs(s.end_date).format('DD/MM/YYYY')}</TableCell>
                    <TableCell>
                      <Badge variant={semesterStatus.variant}>{semesterStatus.label}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
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
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}

        <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
          <DialogContent>
            <form onSubmit={handleSubmit(onSubmit)}>
              <DialogHeader>
                <DialogTitle>{editingSemester ? 'Chỉnh sửa Học kỳ' : 'Thêm Học kỳ mới'}</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Tên học kỳ</Label>
                  <Input placeholder="Ví dụ: Học kỳ 1 năm học 2026-2027" {...register('name')} />
                  {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Ngày bắt đầu</Label>
                    <Input type="date" {...register('start_date')} />
                    {errors.start_date && (
                      <p className="text-xs text-destructive">{errors.start_date.message}</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label>Ngày kết thúc</Label>
                    <Input type="date" {...register('end_date')} />
                    {errors.end_date && (
                      <p className="text-xs text-destructive">{errors.end_date.message}</p>
                    )}
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
                  Hủy
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {editingSemester ? 'Lưu thay đổi' : 'Thêm mới'}
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
                Bạn có chắc chắn muốn xóa học kỳ <strong>{deleteConfirm?.name}</strong> không?
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

export default SemestersPage
