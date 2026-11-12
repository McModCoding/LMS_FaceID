import { useEffect, useState, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  FileText,
  FolderOpen,
  Download,
  ExternalLink,
  Search,
  BookOpen,
  Filter,
  Plus,
  FileCode,
  FileArchive,
  FileSpreadsheet,
  Film,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import { classesApi } from '@/api/classes'
import { materialsApi, Material } from '@/api/materials'
import { Class } from '@/types/class'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface LearningMaterialsPageProps {
  role: 'lecturer' | 'student'
  defaultTab?: 'materials' | 'documents'
}

interface MaterialWithClass extends Material {
  class_code?: string
  subject_name?: string | null
}

export default function LearningMaterialsPage({
  role,
  defaultTab = 'materials',
}: LearningMaterialsPageProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') || defaultTab
  const [classes, setClasses] = useState<Class[]>([])
  const [selectedClassId, setSelectedClassId] = useState<string>('all')
  const [materials, setMaterials] = useState<MaterialWithClass[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [downloadingId, setDownloadingId] = useState<number | null>(null)

  // 1. Fetch user classes
  useEffect(() => {
    let active = true
    classesApi
      .getAll({ page: 1, page_size: 100 })
      .then((res) => {
        if (active) setClasses(res.items)
      })
      .catch(() => {
        toast.error('Không tải được danh sách lớp học')
      })
    return () => {
      active = false
    }
  }, [])

  // 2. Fetch materials across classes
  useEffect(() => {
    let active = true
    setLoading(true)

    const fetchMaterials = async () => {
      try {
        const targetClasses =
          selectedClassId === 'all'
            ? classes
            : classes.filter((c) => c.id.toString() === selectedClassId)

        if (targetClasses.length === 0) {
          if (active) {
            setMaterials([])
            setLoading(false)
          }
          return
        }

        const promises = targetClasses.map(async (c) => {
          try {
            const res = await materialsApi.list(c.id, 1)
            return res.items.map((m) => ({
              ...m,
              class_code: c.code,
              subject_name: c.subject_name,
            }))
          } catch {
            return []
          }
        })

        const results = await Promise.all(promises)
        if (active) {
          setMaterials(results.flat())
          setLoading(false)
        }
      } catch {
        if (active) {
          toast.error('Không tải được danh sách tài liệu')
          setLoading(false)
        }
      }
    }

    if (classes.length > 0) {
      void fetchMaterials()
    } else {
      setLoading(false)
    }

    return () => {
      active = false
    }
  }, [classes, selectedClassId])

  const handleDownload = async (item: Material) => {
    if (!item.has_file) return
    setDownloadingId(item.id)
    try {
      const blob = await materialsApi.download(item.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = item.filename || 'tai-lieu'
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Đã tải tài liệu xuống')
    } catch {
      toast.error('Không thể tải file, vui lòng thử lại sau')
    } finally {
      setDownloadingId(null)
    }
  }

  // Filter materials based on search and tab
  const filteredMaterials = useMemo(() => {
    return materials.filter((m) => {
      const matchSearch =
        m.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (m.description && m.description.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (m.class_code && m.class_code.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (m.subject_name && m.subject_name.toLowerCase().includes(searchTerm.toLowerCase()))

      if (!matchSearch) return false

      // Phân loại:
      // Tab 'materials' (Học liệu): Thường là slide, video, hoặc link học trực tuyến
      // Tab 'documents' (Tài liệu): Các file văn bản (pdf, docx, xlsx, zip, đề cương)
      if (activeTab === 'materials') {
        return m.url !== null || (m.filename && /\.(pptx?|mp4|webm|mkv|zip)$/i.test(m.filename)) || !m.filename
      } else {
        return m.has_file && (m.filename ? !/\.(pptx?|mp4|webm|mkv)$/i.test(m.filename) : true)
      }
    })
  }, [materials, searchTerm, activeTab])

  const getFileIcon = (item: Material) => {
    if (item.url) return <ExternalLink className="h-5 w-5 text-blue-500" />
    const filename = item.filename || ''
    if (/\.(pdf)$/i.test(filename)) return <FileText className="h-5 w-5 text-rose-500" />
    if (/\.(pptx?)$/i.test(filename)) return <FileSpreadsheet className="h-5 w-5 text-amber-500" />
    if (/\.(docx?)$/i.test(filename)) return <FileText className="h-5 w-5 text-blue-500" />
    if (/\.(zip|rar|7z)$/i.test(filename)) return <FileArchive className="h-5 w-5 text-purple-500" />
    if (/\.(mp4|webm|mkv)$/i.test(filename)) return <Film className="h-5 w-5 text-emerald-500" />
    return <FileCode className="h-5 w-5 text-primary" />
  }

  return (
    <div className="space-y-6">

      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-2 border-b border-border/60">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">
            {role === 'lecturer' ? 'Kho tài nguyên giảng dạy' : 'Tài nguyên & Giáo trình học tập'}
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            {activeTab === 'materials' ? 'Học liệu & Bài giảng số' : 'Tài liệu môn học & Giáo trình'}
          </h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {activeTab === 'materials'
              ? 'Tổng hợp bài giảng, slide thuyết trình và liên kết học tập của các lớp học phần.'
              : 'Tổng hợp tài liệu đọc, đề cương chi tiết và tài liệu tham khảo chính thức.'}
          </p>
        </div>

        {role === 'lecturer' && (
          <Button asChild size="sm" className="gap-1.5 self-start sm:self-auto">
            <Link to="/lecturer/classes">
              <Plus className="h-4 w-4" /> Đăng tải học liệu vào lớp
            </Link>
          </Button>
        )}
      </div>

      {/* Tabs Selector: Liên kết chặt chẽ giữa Học liệu & Tài liệu */}
      <div className="flex items-center gap-2 border-b border-border/70 pb-2">
        <button
          type="button"
          onClick={() => setSearchParams({ tab: 'materials' })}
          className={cn(
            'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all',
            activeTab === 'materials'
              ? 'bg-primary text-primary-foreground shadow-xs'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          )}
        >
          <FileText className="h-4 w-4" />
          <span>Học liệu số & Slide</span>
          <Badge variant="secondary" className="ml-1 text-[11px] px-1.5 py-0">
            {materials.filter((m) => m.url || (m.filename && /\.(pptx?|mp4|webm)$/i.test(m.filename)) || !m.filename).length}
          </Badge>
        </button>

        <button
          type="button"
          onClick={() => setSearchParams({ tab: 'documents' })}
          className={cn(
            'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all',
            activeTab === 'documents'
              ? 'bg-primary text-primary-foreground shadow-xs'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          )}
        >
          <FolderOpen className="h-4 w-4" />
          <span>Tài liệu tham khảo & File</span>
          <Badge variant="secondary" className="ml-1 text-[11px] px-1.5 py-0">
            {materials.filter((m) => m.has_file && (m.filename ? !/\.(pptx?|mp4|webm)$/i.test(m.filename) : true)).length}
          </Badge>
        </button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Tìm theo tên học liệu, môn học, mã lớp..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-9 text-sm"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
          <select
            value={selectedClassId}
            onChange={(e) => setSelectedClassId(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-xs sm:text-sm text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="all">-- Tất cả các lớp học phần --</option>
            {classes.map((cls) => (
              <option key={cls.id} value={cls.id.toString()}>
                {cls.code} - {cls.subject_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="p-4 space-y-3">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-10 w-full" />
            </Card>
          ))}
        </div>
      ) : filteredMaterials.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/80 bg-card p-12 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-muted-foreground mb-3">
            {activeTab === 'materials' ? <FileText className="h-6 w-6" /> : <FolderOpen className="h-6 w-6" />}
          </div>
          <h3 className="text-base font-semibold text-foreground">Không tìm thấy tài nguyên nào</h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
            {searchTerm
              ? 'Không có kết quả khớp với từ khóa tìm kiếm. Vui lòng thử từ khóa khác.'
              : 'Chưa có tài liệu hoặc học liệu nào được đăng tải cho các lớp đã chọn.'}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredMaterials.map((item) => {
            const classLink = `/${role}/classes/${item.class_id}?tab=materials`

            return (
              <Card
                key={item.id}
                className="flex flex-col justify-between border-border/80 shadow-2xs hover:shadow-xs hover:border-primary/40 transition-all"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted/70">
                      {getFileIcon(item)}
                    </div>
                    <Badge variant="outline" className="text-[11px] truncate max-w-[130px]">
                      {item.class_code || `Lớp #${item.class_id}`}
                    </Badge>
                  </div>
                  <CardTitle className="text-base font-semibold leading-snug line-clamp-2 mt-2">
                    {item.title}
                  </CardTitle>
                  <CardDescription className="text-xs line-clamp-2 mt-1">
                    {item.description || item.subject_name || 'Không có mô tả thêm.'}
                  </CardDescription>
                </CardHeader>

                <CardContent className="pt-0 space-y-3">
                  <div className="flex flex-wrap items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border/60">
                    <span>
                      {item.filename ? item.filename : item.url ? 'Liên kết trực tuyến' : 'Tài nguyên số'}
                    </span>
                    <span>{new Date(item.created_at).toLocaleDateString('vi-VN')}</span>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    {item.has_file && (
                      <Button
                        size="sm"
                        variant="default"
                        className="flex-1 gap-1.5 text-xs h-8"
                        disabled={downloadingId === item.id}
                        onClick={() => handleDownload(item)}
                      >
                        <Download className="h-3.5 w-3.5" />
                        {downloadingId === item.id ? 'Đang tải...' : 'Tải xuống'}
                      </Button>
                    )}

                    {item.url && (
                      <Button asChild size="sm" variant="default" className="flex-1 gap-1.5 text-xs h-8">
                        <a href={item.url} target="_blank" rel="noopener noreferrer">
                          <ExternalLink className="h-3.5 w-3.5" /> Mở liên kết
                        </a>
                      </Button>
                    )}

                    {/* LIÊN KẾT TRỰC TIẾP VỚI TAB HỌC LIỆU TRONG LỚP */}
                    <Button asChild size="sm" variant="outline" className="text-xs h-8 px-2.5" title="Mở trong tab Học liệu của lớp">
                      <Link to={classLink}>
                        <BookOpen className="h-3.5 w-3.5 text-primary" />
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Banner trợ giúp liên kết */}
      <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 flex items-start gap-3 text-xs text-muted-foreground">
        <Sparkles className="h-4 w-4 text-primary shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-foreground">Liên kết đồng bộ giữa Tài liệu và Học liệu môn học</p>
          <p className="mt-0.5">
            Mọi bài giảng, đề cương và tài liệu tải lên tại đây đều được đồng bộ trực tiếp vào mục &quot;Học liệu&quot; trong từng lớp học phần tương ứng. Bạn có thể nhấn vào biểu tượng quyển sách ở mỗi thẻ tài liệu để mở ngay tab quản lý chi tiết trong lớp.
          </p>
        </div>
      </div>
    </div>
  )
}
