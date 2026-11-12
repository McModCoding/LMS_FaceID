import { Copy } from 'lucide-react'
import { toast } from 'sonner'

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
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

export type TemporaryPasswordState = {
  visible: boolean
  password: string
  title: string
}

type TemporaryPasswordDialogProps = {
  state: TemporaryPasswordState
  onClose: () => void
}

export function TemporaryPasswordDialog({ state, onClose }: TemporaryPasswordDialogProps) {
  const copyPassword = async () => {
    try {
      await navigator.clipboard.writeText(state.password)
      toast.success('Đã sao chép mật khẩu!')
    } catch {
      toast.error('Không thể sao chép. Vui lòng chọn và sao chép mật khẩu thủ công.')
    }
  }

  return (
    <Dialog open={state.visible} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{state.title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-6 text-center">
          <p className="text-sm text-muted-foreground">
            Vui lòng lưu lại mật khẩu này. Mật khẩu chỉ hiển thị 1 lần duy nhất!
          </p>
          <div className="inline-block select-all rounded-md bg-muted px-6 py-3 text-2xl font-bold tracking-wider text-primary">
            {state.password}
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="secondary" onClick={onClose}>
            Đóng
          </Button>
          <Button onClick={copyPassword}>
            <Copy className="mr-2 h-4 w-4" />
            Sao chép mật khẩu
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

type ConfirmTarget = {
  full_name: string
}

type AccountActionDialogsProps = {
  entityLabel: string
  deleteTarget: ConfirmTarget | null
  statusTarget: (ConfirmTarget & { isActive: boolean }) | null
  resetPasswordTarget: ConfirmTarget | null
  onCloseDelete: () => void
  onCloseStatus: () => void
  onCloseResetPassword: () => void
  onDelete: () => void
  onToggleStatus: () => void
  onResetPassword: () => void
}

export function AccountActionDialogs({
  entityLabel,
  deleteTarget,
  statusTarget,
  resetPasswordTarget,
  onCloseDelete,
  onCloseStatus,
  onCloseResetPassword,
  onDelete,
  onToggleStatus,
  onResetPassword,
}: AccountActionDialogsProps) {
  return (
    <>
      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && onCloseDelete()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xác nhận xóa</AlertDialogTitle>
            <AlertDialogDescription>
              Bạn có chắc chắn muốn xóa {entityLabel}{' '}
              <strong>{deleteTarget?.full_name}</strong> không? Tài khoản liên quan cũng sẽ bị
              xóa.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={onDelete}
            >
              Xóa
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={Boolean(statusTarget)} onOpenChange={(open) => !open && onCloseStatus()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xác nhận thao tác</AlertDialogTitle>
            <AlertDialogDescription>
              Bạn có chắc chắn muốn {statusTarget?.isActive ? 'khóa' : 'mở khóa'} tài khoản của{' '}
              {entityLabel} <strong>{statusTarget?.full_name}</strong> không?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction onClick={onToggleStatus}>Đồng ý</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={Boolean(resetPasswordTarget)}
        onOpenChange={(open) => !open && onCloseResetPassword()}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset mật khẩu</AlertDialogTitle>
            <AlertDialogDescription>
              Hệ thống sẽ sinh một mật khẩu ngẫu nhiên mới cho {entityLabel}{' '}
              <strong>{resetPasswordTarget?.full_name}</strong>. Mật khẩu cũ sẽ không còn hiệu lực.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction onClick={onResetPassword}>Reset mật khẩu</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
