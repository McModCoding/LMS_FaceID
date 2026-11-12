import { useEffect, useState } from 'react'
import { Building2, Eye, Pencil, PlusCircle, Power } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { departmentsApi } from '../../api/departments'
import { Department } from '../../types/department'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export default function DepartmentsPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Department | null>(null)
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')

  const load = async () => {
    setLoading(true)
    try { setItems(await departmentsApi.getAll()) }
    catch (error: any) { toast.error(error.response?.data?.error?.message || 'Không thể tải danh sách khoa') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const openForm = (department?: Department) => {
    setEditing(department || null)
    setCode(department?.code || '')
    setName(department?.name || '')
    setOpen(true)
  }
  const submit = async () => {
    if (!name.trim() || (!editing && !code.trim())) return toast.error('Vui lòng nhập đủ mã và tên khoa')
    try {
      if (editing) await departmentsApi.update(editing.id, { name: name.trim() })
      else await departmentsApi.create({ code: code.trim().toUpperCase(), name: name.trim() })
      toast.success(editing ? 'Đã cập nhật khoa' : 'Đã tạo khoa')
      setOpen(false); load()
    } catch (error: any) { toast.error(error.response?.data?.error?.message || 'Không thể lưu khoa') }
  }
  const deactivate = async (department: Department) => {
    if (!window.confirm(`Ngừng sử dụng khoa ${department.name}?`)) return
    try { await departmentsApi.deactivate(department.id); toast.success('Đã ngừng sử dụng khoa'); load() }
    catch (error: any) { toast.error(error.response?.data?.error?.message || 'Không thể ngừng sử dụng khoa') }
  }

  return <Card>
    <CardHeader className="flex flex-row items-center justify-between gap-4">
      <div><CardTitle className="flex items-center gap-2"><Building2 className="h-5 w-5 text-primary" /> Quản lý Khoa</CardTitle><p className="mt-1 text-sm text-muted-foreground">Phân loại sinh viên, giảng viên và môn học theo đơn vị phụ trách.</p></div>
      <Button onClick={() => openForm()}><PlusCircle className="mr-2 h-4 w-4" />Thêm khoa</Button>
    </CardHeader>
    <CardContent>
      {loading ? <div className="space-y-2"><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></div> : <div className="rounded-md border"><Table><TableHeader><TableRow><TableHead>Mã khoa</TableHead><TableHead>Tên khoa</TableHead><TableHead>Trạng thái</TableHead><TableHead className="text-right">Thao tác</TableHead></TableRow></TableHeader><TableBody>{items.map((item) => <TableRow key={item.id}><TableCell className="font-medium">{item.code}</TableCell><TableCell>{item.name}</TableCell><TableCell><Badge variant={item.is_active ? 'success' : 'secondary'}>{item.is_active ? 'Đang sử dụng' : 'Ngừng sử dụng'}</Badge></TableCell><TableCell className="text-right"><Button variant="ghost" size="sm" aria-label={`Xem ${item.name}`} onClick={() => navigate(`/admin/departments/${item.id}`)}><Eye className="h-4 w-4" /></Button><Button variant="ghost" size="sm" aria-label={`Sửa ${item.name}`} onClick={() => openForm(item)}><Pencil className="h-4 w-4" /></Button>{item.is_active && <Button variant="ghost" size="sm" className="text-destructive" aria-label={`Ngừng sử dụng ${item.name}`} onClick={() => deactivate(item)}><Power className="h-4 w-4" /></Button>}</TableCell></TableRow>)}</TableBody></Table></div>}
    </CardContent>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogHeader><DialogTitle>{editing ? 'Cập nhật khoa' : 'Thêm khoa'}</DialogTitle></DialogHeader><div className="space-y-4 py-2"><div className="space-y-2"><Label>Mã khoa</Label><Input value={code} disabled={!!editing} onChange={(event) => setCode(event.target.value)} placeholder="Ví dụ: CNTT" /></div><div className="space-y-2"><Label>Tên khoa</Label><Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Ví dụ: Khoa Công nghệ Thông tin" /></div></div><DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Hủy</Button><Button onClick={submit}>Lưu</Button></DialogFooter></DialogContent></Dialog>
  </Card>
}
