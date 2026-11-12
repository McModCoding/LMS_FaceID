import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { Plus, Trash2, UsersRound } from 'lucide-react'
import { toast } from 'sonner'

import { classesApi } from '@/api/classes'
import { Group, learningApi } from '@/api/learning'
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { ClassStudent } from '@/types/class'

import { getApiErrorMessage } from '@/lib/api-error'

type GroupsPanelProps = {
  classId: number
  canManage?: boolean
}

export function GroupsPanel({ classId, canManage = false }: GroupsPanelProps) {
  const [items, setItems] = useState<Group[]>([])
  const [students, setStudents] = useState<ClassStudent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState('')
  const [groupCount, setGroupCount] = useState('2')
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [selectedStudents, setSelectedStudents] = useState<Record<number, string>>({})
  const [deletingGroup, setDeletingGroup] = useState<Group | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setItems(await learningApi.groups(classId))
      if (canManage) {
        setStudents(
          (
            await classesApi.getStudents(classId, {
              page: 1,
              page_size: 100,
              status: 'enrolled',
            })
          ).items,
        )
      }
    } catch (cause) {
      setError(getApiErrorMessage(cause, 'Không thể tải danh sách nhóm.'))
    } finally {
      setLoading(false)
    }
  }, [canManage, classId])

  useEffect(() => {
    void load()
  }, [load])

  const groupedIds = useMemo(
    () => new Set(items.flatMap((group) => group.members.map((member) => member.student_id))),
    [items],
  )

  const runMutation = async (action: () => Promise<void>, fallback: string) => {
    setSaving(true)
    try {
      await action()
      await load()
    } catch (cause) {
      toast.error(getApiErrorMessage(cause, fallback))
    } finally {
      setSaving(false)
    }
  }

  const create = async (event: FormEvent) => {
    event.preventDefault()
    await runMutation(async () => {
      await learningApi.createGroup(classId, name)
      setName('')
      setCreateOpen(false)
      toast.success('Đã tạo nhóm.')
    }, 'Không thể tạo nhóm.')
  }

  const randomize = async () => {
    await runMutation(async () => {
      await learningApi.randomizeGroups(classId, {
        group_count: Number(groupCount),
        replace_existing: replaceExisting,
      })
      toast.success('Đã chia nhóm ngẫu nhiên.')
    }, 'Không thể chia nhóm.')
  }

  const addMember = async (group: Group) => {
    const studentId = Number(selectedStudents[group.id])
    if (!studentId) return
    await runMutation(async () => {
      await learningApi.addMember(group.id, studentId)
      setSelectedStudents((current) => ({ ...current, [group.id]: '' }))
    }, 'Không thể thêm thành viên.')
  }

  const removeMember = async (group: Group, studentId: number) => {
    await runMutation(async () => {
      await learningApi.removeMember(group.id, studentId)
    }, 'Không thể xóa thành viên khỏi nhóm.')
  }

  const removeGroup = async () => {
    if (!deletingGroup) return
    await runMutation(async () => {
      await learningApi.deleteGroup(deletingGroup.id)
      setDeletingGroup(null)
      toast.success('Đã xóa nhóm.')
    }, 'Không thể xóa nhóm.')
  }

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle className="text-base">Nhóm học tập</CardTitle>
          <CardDescription>Mỗi sinh viên chỉ thuộc tối đa một nhóm trong lớp.</CardDescription>
        </div>
        {canManage && (
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Tạo nhóm
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {canManage && (
          <div className="flex flex-wrap items-end gap-2 rounded-md border bg-muted/20 p-3">
            <div className="space-y-1.5">
              <Label htmlFor="group-count">Số nhóm</Label>
              <Input
                id="group-count"
                className="w-28"
                type="number"
                min="1"
                max="100"
                value={groupCount}
                onChange={(event) => setGroupCount(event.target.value)}
              />
            </div>
            <label className="flex h-10 items-center gap-2 text-sm">
              <Switch checked={replaceExisting} onCheckedChange={setReplaceExisting} />
              Thay nhóm hiện có
            </label>
            <Button variant="outline" disabled={saving} onClick={randomize}>
              <UsersRound className="mr-2 h-4 w-4" />
              Chia ngẫu nhiên
            </Button>
          </div>
        )}

        {loading ? (
          <>
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </>
        ) : error ? (
          <div className="rounded-md border border-destructive/40 p-4 text-sm">
            <p className="text-destructive">{error}</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={load}>
              Thử lại
            </Button>
          </div>
        ) : items.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {items.map((group) => (
              <div className="rounded-md border p-3" key={group.id}>
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium">{group.name}</p>
                  {canManage && (
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Xóa ${group.name}`}
                      onClick={() => setDeletingGroup(group)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
                <div className="mt-2 space-y-1.5">
                  {group.members.length ? (
                    group.members.map((member) => (
                      <div
                        className="flex items-center justify-between gap-2 rounded bg-muted/30 px-2 py-1.5 text-sm"
                        key={member.student_id}
                      >
                        <span>
                          {member.full_name} · {member.student_code}
                        </span>
                        {canManage && (
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7"
                            aria-label={`Xóa ${member.full_name} khỏi ${group.name}`}
                            disabled={saving}
                            onClick={() => removeMember(group, member.student_id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">Chưa có thành viên.</p>
                  )}
                </div>
                {canManage && (
                  <div className="mt-3 flex gap-2">
                    <Select
                      value={selectedStudents[group.id] || ''}
                      onValueChange={(value) =>
                        setSelectedStudents((current) => ({ ...current, [group.id]: value }))
                      }
                    >
                      <SelectTrigger className="min-w-0 flex-1">
                        <SelectValue placeholder="Chọn sinh viên" />
                      </SelectTrigger>
                      <SelectContent>
                        {students
                          .filter((student) => !groupedIds.has(student.student_id))
                          .map((student) => (
                            <SelectItem key={student.student_id} value={String(student.student_id)}>
                              {student.full_name} · {student.student_code}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                    <Button variant="outline" disabled={saving} onClick={() => addMember(group)}>
                      Thêm
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded-md border border-dashed py-10 text-center text-sm text-muted-foreground">
            Chưa có nhóm nào.{' '}
            {canManage
              ? 'Tạo thủ công hoặc chia ngẫu nhiên để bắt đầu.'
              : 'Giảng viên chưa phân nhóm cho lớp.'}
          </p>
        )}
      </CardContent>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <form onSubmit={create}>
            <DialogHeader>
              <DialogTitle>Tạo nhóm</DialogTitle>
              <DialogDescription>
                Tạo nhóm trống, sau đó thêm sinh viên chưa thuộc nhóm khác.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <Label htmlFor="group-name">Tên nhóm</Label>
              <Input
                id="group-name"
                required
                maxLength={100}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                Hủy
              </Button>
              <Button type="submit" disabled={saving}>
                Tạo nhóm
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(deletingGroup)}
        onOpenChange={(value) => !value && setDeletingGroup(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xóa {deletingGroup?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Nhóm và danh sách thành viên trong nhóm sẽ bị xóa. Sinh viên vẫn còn trong lớp học
              phần.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={saving}
              onClick={removeGroup}
            >
              Xóa nhóm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  )
}
