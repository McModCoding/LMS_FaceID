import { ConflictItem } from '../../types/conflict'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { AlertCircle } from 'lucide-react'
import dayjs from 'dayjs'

interface ConflictDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title?: string
  message?: string
  conflicts: ConflictItem[]
}

export const ConflictDialog = ({
  open,
  onOpenChange,
  title = 'Phát hiện xung đột lịch học',
  message = 'Không thể thực hiện do có xung đột với lịch học khác:',
  conflicts,
}: ConflictDialogProps) => {
  const getConflictTypeBadge = (type: string) => {
    switch (type) {
      case 'room':
        return <Badge variant="destructive">Trùng phòng</Badge>
      case 'lecturer':
        return <Badge variant="warning">Trùng giảng viên</Badge>
      case 'student':
        return <Badge variant="secondary">Trùng sinh viên</Badge>
      default:
        return <Badge variant="outline">{type}</Badge>
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-foreground">
            {message}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="flex-1 overflow-auto rounded-md border my-2">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Loại xung đột</TableHead>
                <TableHead>Mã lớp</TableHead>
                <TableHead>Ngày</TableHead>
                <TableHead>Giờ</TableHead>
                <TableHead>Phòng / Đối tượng</TableHead>
                <TableHead>Chi tiết</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {conflicts.map((c, idx) => (
                <TableRow key={idx}>
                  <TableCell>{getConflictTypeBadge(c.conflict_type)}</TableCell>
                  <TableCell className="font-semibold">{c.class_code}</TableCell>
                  <TableCell>{dayjs(c.date).format('DD/MM/YYYY')}</TableCell>
                  <TableCell>{c.start_time?.slice(0, 5)} - {c.end_time?.slice(0, 5)}</TableCell>
                  <TableCell>{c.conflicting_entity || c.room}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{c.message}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <AlertDialogFooter>
          <AlertDialogAction onClick={() => onOpenChange(false)}>
            Đã hiểu
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
