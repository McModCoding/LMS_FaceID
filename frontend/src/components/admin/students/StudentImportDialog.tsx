import { ChangeEvent, useRef, useState } from 'react'
import dayjs from 'dayjs'
import axios from 'axios'
import { AlertTriangle, FileSpreadsheet, Upload } from 'lucide-react'
import { toast } from 'sonner'

import { studentsApi } from '@/api/students'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getApiErrorMessage } from '@/lib/api-error'
import { downloadBlob } from '@/lib/download'
import { StudentImportPreview } from '@/types/student'

type StudentImportDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onImported: () => void | Promise<void>
}

export function StudentImportDialog({
  open,
  onOpenChange,
  onImported,
}: StudentImportDialogProps) {
  const [step, setStep] = useState<1 | 2>(1)
  const [uploading, setUploading] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [preview, setPreview] = useState<StudentImportPreview | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const close = () => {
    onOpenChange(false)
    setStep(1)
    setPreview(null)
  }

  const downloadTemplate = async () => {
    try {
      downloadBlob(await studentsApi.downloadTemplate(), 'mau_import_sinh_vien.xlsx')
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Không thể tải file mẫu'))
    }
  }

  const readFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      setPreview(await studentsApi.importPreview(file))
      setStep(2)
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Tải file Excel thất bại'))
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const confirmImport = async () => {
    if (!preview?.valid_rows.length) return
    setConfirming(true)
    try {
      const excelBlob = await studentsApi.importConfirm(preview.valid_rows)
      downloadBlob(
        excelBlob,
        `mat_khau_tam_sinh_vien_${dayjs().format('YYYYMMDD_HHmmss')}.xlsx`,
      )
      close()
      await onImported()
      toast.success('Import hoàn tất. Kiểm tra file mật khẩu tạm đã tải về để biết các tài khoản được tạo.')
    } catch (error) {
      let message = getApiErrorMessage(error, 'Nhập dữ liệu thất bại')
      if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
        try {
          message = getApiErrorMessage({ response: { data: JSON.parse(await error.response.data.text()) } }, message)
        } catch {
          // Giữ thông báo dự phòng nếu phản hồi không phải JSON.
        }
      }
      toast.error(message)
    } finally {
      setConfirming(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(value) => (value ? onOpenChange(true) : close())}>
      <DialogContent className="flex max-h-[85vh] max-w-4xl flex-col">
        <DialogHeader>
          <DialogTitle>Import danh sách sinh viên từ Excel</DialogTitle>
        </DialogHeader>

        {step === 1 && (
          <div className="space-y-4 py-6">
            <div className="flex items-center justify-between rounded-lg bg-muted p-4">
              <div>
                <h4 className="text-sm font-semibold">Chưa có file mẫu?</h4>
                <p className="text-xs text-muted-foreground">
                  Tải file mẫu, thay dòng ví dụ bằng dữ liệu thật. Mã khoa là bắt buộc và phải có trong danh mục Khoa.
                </p>
                <p className="text-xs text-muted-foreground">Chỉ tạo sinh viên mới; MSSV đã có sẽ được bỏ qua, không cập nhật khoa.</p>
              </div>
              <Button variant="outline" size="sm" onClick={downloadTemplate}>
                <FileSpreadsheet className="mr-2 h-4 w-4" />
                Tải file mẫu
              </Button>
            </div>

            <div className="space-y-4 rounded-lg border-2 border-dashed p-12 text-center">
              <Upload className="mx-auto h-12 w-12 text-muted-foreground" />
              <div className="space-y-1">
                <p className="text-sm font-medium">Chọn file Excel để xem trước dữ liệu</p>
                <p className="text-xs text-muted-foreground">Định dạng hỗ trợ: .xlsx (tối đa 500 dòng)</p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx"
                className="hidden"
                id="excel-upload"
                onChange={readFile}
              />
              <Button
                variant="secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? 'Đang đọc file...' : 'Chọn file từ máy tính'}
              </Button>
            </div>
          </div>
        )}

        {step === 2 && preview && (
          <div className="flex min-h-0 flex-1 flex-col space-y-4 py-2">
            <Alert variant="warning">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Kiểm tra dữ liệu trước khi xác nhận</AlertTitle>
              <AlertDescription>
                Hệ thống chỉ tạo tài khoản cho các dòng <strong>Hợp lệ</strong>. File mật khẩu
                tạm sẽ tự động tải về sau khi hoàn tất.
              </AlertDescription>
            </Alert>

            <Tabs defaultValue="valid" className="flex min-h-0 flex-1 flex-col">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="valid">Hợp lệ ({preview.valid_count})</TabsTrigger>
                <TabsTrigger value="warning">Cảnh báo ({preview.warning_count})</TabsTrigger>
                <TabsTrigger value="error">Lỗi ({preview.error_count})</TabsTrigger>
              </TabsList>

              <TabsContent value="valid" className="mt-2 min-h-0 flex-1 overflow-hidden rounded-md border">
                <ScrollArea className="h-64">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-16">Dòng</TableHead>
                        <TableHead>Mã SV</TableHead>
                        <TableHead>Họ và tên</TableHead>
                        <TableHead>Lớp HC</TableHead>
                        <TableHead>Khoa</TableHead>
                        <TableHead>Email</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {preview.valid_rows.map((row) => (
                        <TableRow key={row.row}>
                          <TableCell>{row.row}</TableCell>
                          <TableCell className="font-medium">{row.student_code}</TableCell>
                          <TableCell>{row.full_name}</TableCell>
                          <TableCell>{row.admin_class || '-'}</TableCell>
                          <TableCell>{row.department_code} · {row.department_name}</TableCell>
                          <TableCell>{row.email || '-'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="warning" className="mt-2 min-h-0 flex-1 overflow-hidden rounded-md border">
                <ScrollArea className="h-64">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-16">Dòng</TableHead>
                        <TableHead>Mã SV</TableHead>
                        <TableHead>Họ và tên</TableHead>
                        <TableHead>Cảnh báo</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {preview.warning_rows.map((row) => (
                        <TableRow key={row.row}>
                          <TableCell>{row.row}</TableCell>
                          <TableCell className="font-medium">{row.student_code}</TableCell>
                          <TableCell>{row.full_name}</TableCell>
                          <TableCell className="text-warning">{row.reason}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="error" className="mt-2 min-h-0 flex-1 overflow-hidden rounded-md border">
                <ScrollArea className="h-64">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-16">Dòng</TableHead>
                        <TableHead>Mã SV</TableHead>
                        <TableHead>Họ và tên</TableHead>
                        <TableHead>Lý do lỗi</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {preview.error_rows.map((row) => (
                        <TableRow key={row.row}>
                          <TableCell>{row.row}</TableCell>
                          <TableCell className="font-medium">{row.student_code || '-'}</TableCell>
                          <TableCell>{row.full_name || '-'}</TableCell>
                          <TableCell className="text-destructive">{row.reason}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </div>
        )}

        <DialogFooter className="border-t pt-4">
          {step === 2 && (
            <Button variant="outline" onClick={() => setStep(1)}>
              Chọn file khác
            </Button>
          )}
          <Button variant="ghost" onClick={close}>
            Đóng
          </Button>
          {step === 2 && (
            <Button onClick={confirmImport} disabled={confirming || preview?.valid_count === 0}>
              {confirming ? 'Đang xử lý...' : `Xác nhận Import (${preview?.valid_count || 0})`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
