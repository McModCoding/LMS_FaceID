import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  UserPlus,
  Upload,
  UserMinus,
  Search,
  AlertTriangle,
} from 'lucide-react'
import dayjs from 'dayjs'
import { toast } from 'sonner'

import { Class, ClassStudent, EnrollmentImportPreview } from '../../types/class'
import { Student } from '../../types/student'
import { classesApi } from '../../api/classes'
import { studentsApi } from '../../api/students'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { getApiErrorMessage as getBackendErrorMessage } from '@/lib/api-error'

interface ClassStudentsTabProps {
  classData: Class
  canManage: boolean // true for Admin, false for Lecturer/Student
  onClassUpdated?: () => void
}

export const ClassStudentsTab: React.FC<ClassStudentsTabProps> = ({
  classData,
  canManage,
  onClassUpdated,
}) => {
  const [students, setStudents] = useState<ClassStudent[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const listRequestId = useRef(0)
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // Add Manual Student states
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [allAvailableStudents, setAllAvailableStudents] = useState<Student[]>([])
  const [studentSearch, setStudentSearch] = useState('')
  const [debouncedStudentSearch, setDebouncedStudentSearch] = useState('')
  const [availablePage, setAvailablePage] = useState(1)
  const [availableTotal, setAvailableTotal] = useState(0)
  const [availableError, setAvailableError] = useState('')
  const [rosterError, setRosterError] = useState('')
  const [rosterLoading, setRosterLoading] = useState(false)
  const [enrolledIds, setEnrolledIds] = useState<number[]>([])
  const [availableRetry, setAvailableRetry] = useState(0)
  const [rosterRetry, setRosterRetry] = useState(0)
  const [selectedStudentIds, setSelectedStudentIds] = useState<number[]>([])
  const [loadingAvailable, setLoadingAvailable] = useState(false)
  const [submittingAdd, setSubmittingAdd] = useState(false)

  // Drop student state
  const [dropConfirmStudent, setDropConfirmStudent] = useState<ClassStudent | null>(null)

  // Import states
  const [isImportModalOpen, setIsImportModalOpen] = useState(false)
  const [importStep, setImportStep] = useState<1 | 2>(1)
  const [uploading, setUploading] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [importPreview, setImportPreview] = useState<EnrollmentImportPreview | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handleSearchChange = (val: string) => {
    setSearch(val)
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(val)
      setPage(1)
    }, 300)
  }

  const fetchClassStudents = useCallback(async () => {
    const requestId = ++listRequestId.current
    setLoading(true)
    setLoadError('')
    try {
      const res = await classesApi.getStudents(classData.id, {
        page,
        page_size: pageSize,
        q: debouncedSearch.trim() || undefined,
      })
      if (requestId === listRequestId.current) {
        setStudents(res.items)
        setTotal(res.total)
      }
    } catch (error: unknown) {
      if (requestId === listRequestId.current) setLoadError(getBackendErrorMessage(error, 'Không thể tải danh sách sinh viên lớp'))
    } finally {
      if (requestId === listRequestId.current) setLoading(false)
    }
  }, [classData.id, page, pageSize, debouncedSearch])

  useEffect(() => {
    void fetchClassStudents()
    return () => { listRequestId.current += 1 }
  }, [fetchClassStudents])

  // Fetch available students when opening Add Modal
  const openAddModal = () => {
    setLoadingAvailable(true)
    setRosterLoading(true)
    setAllAvailableStudents([])
    setEnrolledIds([])
    setIsAddModalOpen(true)
    setSelectedStudentIds([])
    setStudentSearch('')
    setDebouncedStudentSearch('')
    setAvailablePage(1)
  }

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedStudentSearch(studentSearch.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [studentSearch])

  useEffect(() => {
    if (!isAddModalOpen) return
    let active = true
    setLoadingAvailable(true); setAvailableError('')
    void studentsApi.getAll({ page: availablePage, page_size: 20, status: 'studying', search: debouncedStudentSearch || undefined }).then((result) => {
      if (active) { setAllAvailableStudents(result.items); setAvailableTotal(result.total) }
    }).catch((error: unknown) => {
      if (active) { setAllAvailableStudents([]); setAvailableError(getBackendErrorMessage(error, 'Không thể tải danh sách sinh viên.')) }
    }).finally(() => { if (active) setLoadingAvailable(false) })
    return () => { active = false }
  }, [isAddModalOpen, availablePage, debouncedStudentSearch, availableRetry])

  useEffect(() => {
    if (!isAddModalOpen) return
    let active = true
    setRosterLoading(true); setRosterError(''); setEnrolledIds([])
    const loadRoster = async () => {
      const first = await classesApi.getStudents(classData.id, { page: 1, page_size: 100, status: 'enrolled' })
      const pages = Math.ceil(first.total / 100)
      const rest = await Promise.all(Array.from({ length: Math.max(0, pages - 1) }, (_, index) => classesApi.getStudents(classData.id, { page: index + 2, page_size: 100, status: 'enrolled' })))
      return [first, ...rest].flatMap((result) => result.items.map((item) => item.student_id))
    }
    void loadRoster().then((ids) => { if (active) setEnrolledIds(ids) }).catch((error: unknown) => {
      if (active) setRosterError(getBackendErrorMessage(error, 'Không thể kiểm tra danh sách đã ghi danh.'))
    }).finally(() => { if (active) setRosterLoading(false) })
    return () => { active = false }
  }, [isAddModalOpen, classData.id, rosterRetry])

  const handleEnrollManual = async () => {
    if (selectedStudentIds.length === 0) return
    setSubmittingAdd(true)
    try {
      await classesApi.enrollStudents(classData.id, selectedStudentIds)
      toast.success(`Đã thêm ${selectedStudentIds.length} sinh viên vào lớp`)
      setIsAddModalOpen(false)
      fetchClassStudents()
      onClassUpdated?.()
    } catch (error: unknown) {
      const msg = getBackendErrorMessage(error, 'Không thể thêm sinh viên vào lớp')
      toast.error(msg)
    } finally {
      setSubmittingAdd(false)
    }
  }

  const handleDropStudent = async () => {
    if (!dropConfirmStudent) return
    try {
      await classesApi.dropStudent(classData.id, dropConfirmStudent.student_id)
      toast.success(`Đã rút sinh viên ${dropConfirmStudent.full_name} khỏi lớp`)
      setDropConfirmStudent(null)
      fetchClassStudents()
      onClassUpdated?.()
    } catch (error: unknown) {
      const msg = getBackendErrorMessage(error, 'Không thể rút sinh viên')
      toast.error(msg)
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const preview = await classesApi.importPreview(classData.id, file)
      setImportPreview(preview)
      setImportStep(2)
    } catch (error: unknown) {
      const msg = getBackendErrorMessage(error, 'Tải file Excel thất bại')
      toast.error(msg)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleConfirmImport = async () => {
    if (!importPreview || !importPreview.valid_rows || importPreview.valid_rows.length === 0) return
    setConfirming(true)
    try {
      await classesApi.importConfirm(classData.id, importPreview.valid_rows)
      toast.success(`Đã thêm thành công ${importPreview.valid_count} sinh viên vào lớp`)
      setIsImportModalOpen(false)
      setImportStep(1)
      setImportPreview(null)
      fetchClassStudents()
      onClassUpdated?.()
    } catch (error: unknown) {
      const msg = getBackendErrorMessage(error, 'Ghi danh sinh viên thất bại')
      toast.error(msg)
    } finally {
      setConfirming(false)
    }
  }

  const isClassClosed = classData.status === 'closed'

  return (
    <TooltipProvider>
      <div className="space-y-4">

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="relative w-64">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Tìm kiếm MSSV, họ tên..."
                className="pl-8"
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
              />
            </div>
            <div className="text-sm text-muted-foreground ml-2">
              Sĩ số: <strong className="text-foreground">{classData.enrolled_count}</strong> / {classData.max_students}
            </div>
          </div>

          {canManage && !isClassClosed && (
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => setIsImportModalOpen(true)}>
                <Upload className="mr-2 h-4 w-4" /> Import Excel
              </Button>
              <Button onClick={openAddModal}>
                <UserPlus className="mr-2 h-4 w-4" /> Thêm sinh viên
              </Button>
            </div>
          )}
        </div>

        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : loadError ? (
          <div role="alert" className="rounded-lg border p-6 text-center"><p>{loadError}</p><Button variant="outline" className="mt-3" onClick={() => void fetchClassStudents()}>Thử lại</Button></div>
        ) : students.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground border rounded-lg bg-card">
            {debouncedSearch
              ? 'Không tìm thấy sinh viên nào khớp với tìm kiếm.'
              : 'Chưa có sinh viên nào trong lớp học này. Dùng “Thêm sinh viên” hoặc Import Excel nếu bạn được phép quản lý lớp.'}
          </div>
        ) : (
          <div className="rounded-md border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16 text-center">STT</TableHead>
                  <TableHead>Mã sinh viên</TableHead>
                  <TableHead>Họ và tên</TableHead>
                  <TableHead>Trạng thái</TableHead>
                  <TableHead>Ngày ghi danh</TableHead>
                  {canManage && !isClassClosed && <TableHead className="text-right">Thao tác</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {students.map((st, idx) => (
                  <TableRow key={st.id}>
                    <TableCell className="text-center">{(page - 1) * pageSize + idx + 1}</TableCell>
                    <TableCell className="font-semibold">{st.student_code}</TableCell>
                    <TableCell>{st.full_name}</TableCell>
                    <TableCell>
                      {st.status === 'enrolled' ? (
                        <Badge variant="success">Đang học</Badge>
                      ) : (
                        <Badge variant="secondary">Đã rút</Badge>
                      )}
                    </TableCell>
                    <TableCell>{dayjs(st.enrolled_at).format('DD/MM/YYYY HH:mm')}</TableCell>
                    {canManage && !isClassClosed && (
                      <TableCell className="text-right">
                        {st.status === 'enrolled' && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:text-destructive"
                                aria-label={`Rút ${st.full_name} khỏi lớp`}
                                onClick={() => setDropConfirmStudent(st)}
                              >
                                <UserMinus className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Rút khỏi lớp</TooltipContent>
                          </Tooltip>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {!loading && !loadError && total > 0 && (
          <div className="flex items-center justify-between px-2 py-2">
            <div className="text-sm text-muted-foreground">Tổng cộng: {total} sinh viên</div>
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

        <Dialog open={isAddModalOpen} onOpenChange={setIsAddModalOpen}>
          <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
            <DialogHeader>
              <DialogTitle>Thêm sinh viên vào lớp học</DialogTitle>
            </DialogHeader>

            <div className="space-y-3 py-2 flex-1 flex flex-col min-h-0">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Lọc danh sách sinh viên theo MSSV, tên..."
                  className="pl-8"
                  value={studentSearch}
                  onChange={(e) => { setStudentSearch(e.target.value); setAvailablePage(1) }}
                />
              </div>

              {loadingAvailable ? (
                <div className="space-y-2 py-4">
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                </div>
              ) : availableError ? (
                <div role="alert" className="space-y-2"><p>{availableError}</p><Button variant="outline" size="sm" onClick={() => setAvailableRetry((value) => value + 1)}>Thử tải lại danh sách</Button></div>
              ) : (
                <ScrollArea className="flex-1 border rounded-md h-[300px]">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12 text-center">Chọn</TableHead>
                        <TableHead>MSSV</TableHead>
                        <TableHead>Họ và tên</TableHead>
                        <TableHead>Lớp HC</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {allAvailableStudents.map((s) => {
                          const isSelected = selectedStudentIds.includes(s.id)
                          const alreadyInClass = enrolledIds.includes(s.id)

                          return (
                            <TableRow
                              key={s.id}
                              className={alreadyInClass ? 'opacity-50' : 'cursor-pointer hover:bg-muted/50'}
                              onClick={() => {
                                if (alreadyInClass || rosterLoading || rosterError) return
                                setSelectedStudentIds((prev) =>
                                  isSelected ? prev.filter((id) => id !== s.id) : [...prev, s.id]
                                )
                              }}
                            >
                              <TableCell className="text-center">
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  disabled={alreadyInClass || rosterLoading || !!rosterError}
                                  aria-label={`Chọn ${s.full_name} (${s.student_code})`}
                                  onClick={(e) => e.stopPropagation()}
                                  onChange={(e) => {
                                    e.stopPropagation()
                                    setSelectedStudentIds((prev) =>
                                      isSelected ? prev.filter((id) => id !== s.id) : [...prev, s.id]
                                    )
                                  }}
                                />
                              </TableCell>
                              <TableCell className="font-medium">{s.student_code}</TableCell>
                              <TableCell>{s.full_name}</TableCell>
                              <TableCell>
                                {s.admin_class || '-'}
                                {alreadyInClass && (
                                  <Badge variant="outline" className="ml-2 text-xs">
                                    Đã trong lớp
                                  </Badge>
                                )}
                              </TableCell>
                            </TableRow>
                          )
                        })}
                    </TableBody>
                  </Table>
                </ScrollArea>
              )}
              {rosterLoading && <p className="text-sm text-muted-foreground">Đang kiểm tra sinh viên đã ghi danh…</p>}
              {rosterError && <div role="alert" className="space-y-2"><p>{rosterError}</p><Button variant="outline" size="sm" onClick={() => setRosterRetry((value) => value + 1)}>Thử kiểm tra lại</Button></div>}
              {!loadingAvailable && !availableError && <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>{availableTotal === 0 ? 'Không tìm thấy sinh viên. Hãy thử từ khóa khác.' : `Tìm thấy ${availableTotal} sinh viên`}</span>{availableTotal > 20 && <div className="flex items-center gap-2"><Button variant="outline" size="sm" disabled={availablePage <= 1} onClick={() => setAvailablePage((page) => page - 1)}>Trước</Button><span>Trang {availablePage} / {Math.ceil(availableTotal / 20)}</span><Button variant="outline" size="sm" disabled={availablePage * 20 >= availableTotal} onClick={() => setAvailablePage((page) => page + 1)}>Sau</Button></div>}</div>}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setIsAddModalOpen(false)}>
                Hủy
              </Button>
              <Button onClick={handleEnrollManual} disabled={submittingAdd || rosterLoading || !!rosterError || selectedStudentIds.length === 0}>
                {submittingAdd ? 'Đang thêm...' : `Thêm ${selectedStudentIds.length} sinh viên`}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={isImportModalOpen} onOpenChange={setIsImportModalOpen}>
          <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col">
            <DialogHeader>
              <DialogTitle>Import danh sách sinh viên vào lớp từ Excel</DialogTitle>
            </DialogHeader>

            {importStep === 1 && (
              <div className="py-6 space-y-4">
                <div className="border-2 border-dashed rounded-lg p-12 text-center space-y-4">
                  <Upload className="mx-auto h-12 w-12 text-muted-foreground" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Chọn hoặc kéo thả file Excel danh sách MSSV vào đây</p>
                    <p className="text-xs text-muted-foreground">Định dạng hỗ trợ: .xlsx (cần cột mssv hoặc student_code)</p>
                  </div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx"
                    className="hidden"
                    onChange={handleFileChange}
                  />
                  <Button variant="secondary" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
                    {uploading ? 'Đang phân tích...' : 'Chọn file từ máy tính'}
                  </Button>
                </div>
              </div>
            )}

            {importStep === 2 && importPreview && (
              <div className="flex-1 flex flex-col min-h-0 space-y-4 py-2">
                <Alert variant="warning">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Kiểm tra kết quả xem trước</AlertTitle>
                  <AlertDescription>
                    Hệ thống sẽ ghi danh các dòng <strong>Hợp lệ</strong> vào lớp học. Các dòng cảnh báo/lỗi (như trùng lịch, sinh viên không tồn tại) sẽ bị bỏ qua.
                  </AlertDescription>
                </Alert>

                <Tabs defaultValue="valid" className="flex-1 flex flex-col min-h-0">
                  <TabsList className="grid grid-cols-3 w-full">
                    <TabsTrigger value="valid">Hợp lệ ({importPreview.valid_count})</TabsTrigger>
                    <TabsTrigger value="warning">Cảnh báo ({importPreview.warning_count})</TabsTrigger>
                    <TabsTrigger value="error">Lỗi ({importPreview.error_count})</TabsTrigger>
                  </TabsList>

                  <TabsContent value="valid" className="flex-1 mt-2 border rounded-md min-h-0 overflow-hidden">
                    <ScrollArea className="h-60">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-16">Dòng</TableHead>
                            <TableHead>Mã SV</TableHead>
                            <TableHead>Họ và tên</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {importPreview.valid_rows.map((r, i) => (
                            <TableRow key={i}>
                              <TableCell>{r.row}</TableCell>
                              <TableCell className="font-semibold">{r.student_code}</TableCell>
                              <TableCell>{r.full_name || '-'}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </ScrollArea>
                  </TabsContent>

                  <TabsContent value="warning" className="flex-1 mt-2 border rounded-md min-h-0 overflow-hidden">
                    <ScrollArea className="h-60">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-16">Dòng</TableHead>
                            <TableHead>Mã SV</TableHead>
                            <TableHead>Cảnh báo / Xung đột</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {importPreview.warning_rows.map((r, i) => (
                            <TableRow key={i}>
                              <TableCell>{r.row}</TableCell>
                              <TableCell className="font-semibold">{r.student_code}</TableCell>
                              <TableCell className="text-warning">{r.reason}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </ScrollArea>
                  </TabsContent>

                  <TabsContent value="error" className="flex-1 mt-2 border rounded-md min-h-0 overflow-hidden">
                    <ScrollArea className="h-60">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-16">Dòng</TableHead>
                            <TableHead>Mã SV</TableHead>
                            <TableHead>Lý do lỗi</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {importPreview.error_rows.map((r, i) => (
                            <TableRow key={i}>
                              <TableCell>{r.row}</TableCell>
                              <TableCell className="font-semibold">{r.student_code || '-'}</TableCell>
                              <TableCell className="text-destructive">{r.reason}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </ScrollArea>
                  </TabsContent>
                </Tabs>
              </div>
            )}

            <DialogFooter className="pt-3 border-t">
              {importStep === 2 && (
                <Button variant="outline" onClick={() => setImportStep(1)}>
                  Chọn file khác
                </Button>
              )}
              <Button variant="ghost" onClick={() => setIsImportModalOpen(false)}>
                Đóng
              </Button>
              {importStep === 2 && (
                <Button onClick={handleConfirmImport} disabled={confirming || importPreview?.valid_count === 0}>
                  {confirming ? 'Đang ghi danh...' : `Xác nhận ghi danh (${importPreview?.valid_count || 0})`}
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <AlertDialog open={!!dropConfirmStudent} onOpenChange={(o) => !o && setDropConfirmStudent(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Xác nhận rút sinh viên</AlertDialogTitle>
              <AlertDialogDescription>
                Bạn có chắc chắn muốn rút sinh viên <strong>{dropConfirmStudent?.full_name}</strong> ({dropConfirmStudent?.student_code}) khỏi lớp học này không?
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Hủy</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={handleDropStudent}
              >
                Rút sinh viên
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </TooltipProvider>
  )
}

