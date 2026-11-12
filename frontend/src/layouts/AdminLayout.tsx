import { useState, useMemo, useEffect } from 'react'
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom'
import {
  Calendar,
  BookOpen,
  Users,
  GraduationCap,
  Menu,
  LogOut,
  KeyRound,
  ChevronRight,
  ChevronDown,
  GalleryVerticalEnd,
  Building2,
  Bell,
  ScanFace,
  LayoutDashboard,
  ScrollText,
  Settings2,
  UserRound,
} from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { ModeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { MobileNavigation } from '@/components/common/MobileNavigation'
import { NotificationBell } from '@/components/common/NotificationBell'
import { AppBreadcrumb, BreadcrumbItem } from '@/components/common/Breadcrumb'

interface SubItem {
  key: string
  label: string
  icon: React.ReactNode
}

interface NavGroup {
  id: string
  label: string
  icon: React.ReactNode
  items: SubItem[]
}

const adminGroups: NavGroup[] = [
  {
    id: 'training',
    label: 'Quản lý Đào tạo',
    icon: <GalleryVerticalEnd className="h-4 w-4" />,
    items: [
      { key: '/admin/classes', label: 'Lớp học phần', icon: <GalleryVerticalEnd className="h-4 w-4" /> },
      { key: '/admin/timetable', label: 'Thời khóa biểu', icon: <Calendar className="h-4 w-4" /> },
    ],
  },
  {
    id: 'people',
    label: 'Người học & Nhân sự',
    icon: <Users className="h-4 w-4" />,
    items: [
      { key: '/admin/students', label: 'Sinh viên', icon: <GraduationCap className="h-4 w-4" /> },
      { key: '/admin/lecturers', label: 'Giảng viên', icon: <Users className="h-4 w-4" /> },
    ],
  },
  {
    id: 'catalog',
    label: 'Danh mục Đào tạo',
    icon: <Building2 className="h-4 w-4" />,
    items: [
      { key: '/admin/departments', label: 'Khoa / Bộ môn', icon: <Building2 className="h-4 w-4" /> },
      { key: '/admin/subjects', label: 'Môn học', icon: <BookOpen className="h-4 w-4" /> },
      { key: '/admin/semesters', label: 'Học kỳ', icon: <Calendar className="h-4 w-4" /> },
    ],
  },
  {
    id: 'system',
    label: 'Hệ thống & Vận hành',
    icon: <Settings2 className="h-4 w-4" />,
    items: [
      { key: '/admin/announcements', label: 'Thông báo hệ thống', icon: <Bell className="h-4 w-4" /> },
      { key: '/admin/face', label: 'Cấu hình FaceID', icon: <ScanFace className="h-4 w-4" /> },
      { key: '/admin/audit-logs', label: 'Nhật ký hệ thống', icon: <ScrollText className="h-4 w-4" /> },
      { key: '/admin/system-info', label: 'Thông số vận hành', icon: <Settings2 className="h-4 w-4" /> },
    ],
  },
]

const flatNavItems: SubItem[] = [
  { key: '/admin/dashboard', label: 'Trang chủ', icon: <LayoutDashboard className="h-4 w-4" /> },
  ...adminGroups.flatMap((g) => g.items),
]

export const AdminLayout = () => {
  const [collapsed, setCollapsed] = useState(false)
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  // Collapsible dropdown state for groups
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({
    training: true,
    people: true,
    catalog: false,
    system: false,
  })

  // Auto-expand group if current path is in that group
  useEffect(() => {
    adminGroups.forEach((group) => {
      if (group.items.some((item) => location.pathname.startsWith(item.key))) {
        setOpenGroups((prev) => ({ ...prev, [group.id]: true }))
      }
    })
  }, [location.pathname])

  const toggleGroup = (groupId: string) => {
    setOpenGroups((prev) => ({
      ...prev,
      [groupId]: !prev[groupId],
    }))
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const initials = user?.username ? user.username.slice(0, 2).toUpperCase() : 'A'

  const breadcrumbs: BreadcrumbItem[] = useMemo(() => {
    const path = location.pathname
    if (path === '/admin/dashboard') return [{ label: 'Trang chủ' }]
    if (path.startsWith('/admin/classes/')) return [{ label: 'Lớp học phần', href: '/admin/classes' }, { label: 'Chi tiết lớp' }]
    if (path === '/admin/classes') return [{ label: 'Lớp học phần' }]
    if (path === '/admin/students') return [{ label: 'Sinh viên' }]
    if (path.startsWith('/admin/students/')) return [{ label: 'Sinh viên', href: '/admin/students' }, { label: 'Hồ sơ' }]
    if (path === '/admin/lecturers') return [{ label: 'Giảng viên' }]
    if (path.startsWith('/admin/lecturers/')) return [{ label: 'Giảng viên', href: '/admin/lecturers' }, { label: 'Hồ sơ' }]
    if (path === '/admin/departments') return [{ label: 'Khoa' }]
    if (path.startsWith('/admin/departments/')) return [{ label: 'Khoa', href: '/admin/departments' }, { label: 'Chi tiết' }]
    if (path === '/admin/subjects') return [{ label: 'Môn học' }]
    if (path === '/admin/semesters') return [{ label: 'Học kỳ' }]
    if (path === '/admin/timetable') return [{ label: 'Thời khóa biểu' }]
    if (path === '/admin/announcements') return [{ label: 'Thông báo hệ thống' }]
    if (path === '/admin/face') return [{ label: 'Cấu hình FaceID' }]
    if (path === '/admin/audit-logs') return [{ label: 'Nhật ký hệ thống' }]
    if (path === '/admin/system-info') return [{ label: 'Thông số vận hành' }]
    return []
  }, [location.pathname])

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <aside
        className={cn(
          'hidden flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-all duration-300 shrink-0 shadow-xs',
          'md:flex',
          collapsed ? 'w-16' : 'w-64'
        )}
      >
        <div className="flex h-14 items-center border-b border-sidebar-border px-3.5 shrink-0 bg-sidebar/50">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0">
            <GalleryVerticalEnd className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="ml-2.5 min-w-0">
              <div className="font-semibold text-sm leading-tight text-sidebar-foreground tracking-tight truncate">LMS FaceID</div>
              <div className="text-[11px] text-sidebar-muted truncate">Quản trị đào tạo</div>
            </div>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto h-7 w-7 text-sidebar-muted hover:text-sidebar-foreground hover:bg-sidebar-accent"
            aria-label={collapsed ? 'Mở rộng thanh điều hướng' : 'Thu gọn thanh điều hướng'}
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
        </div>

        <ScrollArea className="flex-1 py-3">
          <nav className="grid gap-1 px-2.5">
            {/* Trang chủ - Standalone item */}
            <Link
              to="/admin/dashboard"
              className={cn(
                'flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-all duration-150',
                location.pathname === '/admin/dashboard'
                  ? 'bg-primary text-primary-foreground font-semibold shadow-xs'
                  : 'text-sidebar-muted hover:bg-sidebar-accent hover:text-sidebar-foreground'
              )}
              title={collapsed ? 'Trang chủ' : undefined}
            >
              <span className={cn('shrink-0', location.pathname === '/admin/dashboard' ? 'text-primary-foreground' : 'text-sidebar-muted')}>
                <LayoutDashboard className="h-4 w-4" />
              </span>
              {!collapsed && <span className="truncate">Trang chủ</span>}
            </Link>

            {adminGroups.map((group) => {
              const isOpen = openGroups[group.id]
              const hasActiveChild = group.items.some((item) => location.pathname.startsWith(item.key))

              if (collapsed) {
                // Collapsed mode: direct icons with dropdown popup
                return (
                  <DropdownMenu key={group.id}>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className={cn(
                          'w-full h-9 rounded-lg hover:bg-sidebar-accent',
                          hasActiveChild ? 'bg-sidebar-accent text-sidebar-foreground' : 'text-sidebar-muted'
                        )}
                        title={group.label}
                      >
                        {group.icon}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent side="right" align="start" className="w-52">
                      <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {group.label}
                      </div>
                      <DropdownMenuSeparator />
                      {group.items.map((sub) => (
                        <DropdownMenuItem
                          key={sub.key}
                          onClick={() => navigate(sub.key)}
                          className={cn(location.pathname.startsWith(sub.key) && 'bg-accent font-semibold')}
                        >
                          <span className="mr-2">{sub.icon}</span>
                          {sub.label}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )
              }

              return (
                <div key={group.id} className="pt-2">

                  <button
                    type="button"
                    onClick={() => toggleGroup(group.id)}
                    className={cn(
                      'w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors',
                      hasActiveChild
                        ? 'text-sidebar-foreground hover:bg-sidebar-accent/60'
                        : 'text-sidebar-muted hover:text-sidebar-foreground hover:bg-sidebar-accent/50'
                    )}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <span className={cn('shrink-0', hasActiveChild ? 'text-primary' : 'text-sidebar-muted')}>
                        {group.icon}
                      </span>
                      <span className="truncate">{group.label}</span>
                    </div>
                    <ChevronDown
                      className={cn(
                        'h-3.5 w-3.5 shrink-0 transition-transform duration-200',
                        isOpen ? 'rotate-0' : '-rotate-90'
                      )}
                    />
                  </button>

                  {isOpen && (
                    <div className="grid gap-0.5 pl-3 mt-1 border-l border-sidebar-border/80 ml-3.5">
                      {group.items.map((sub) => {
                        const active = location.pathname.startsWith(sub.key)
                        return (
                          <Link
                            key={sub.key}
                            to={sub.key}
                            className={cn(
                              'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors',
                              active
                                ? 'bg-primary text-primary-foreground font-semibold shadow-2xs'
                                : 'text-sidebar-muted hover:bg-sidebar-accent hover:text-sidebar-foreground'
                            )}
                          >
                            <span className={cn('shrink-0', active ? 'text-primary-foreground' : 'text-sidebar-muted')}>
                              {sub.icon}
                            </span>
                            <span className="truncate">{sub.label}</span>
                          </Link>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </nav>
        </ScrollArea>

        <div className="border-t border-sidebar-border p-2.5 shrink-0 bg-sidebar/50">
          <div className="flex items-center gap-1.5">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  className={cn('h-auto py-2 hover:bg-sidebar-accent flex-1', collapsed ? 'justify-center px-0' : 'justify-start gap-2.5 px-2')}
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-semibold shadow-xs">
                    {initials}
                  </div>
                  {!collapsed && (
                    <div className="text-left min-w-0 flex-1 leading-tight">
                      <p className="truncate text-sm font-semibold text-sidebar-foreground">{user?.username}</p>
                      <p className="truncate text-[11px] text-sidebar-muted">Quản trị viên</p>
                    </div>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" side="right" className="w-52">
                <DropdownMenuItem onClick={() => navigate('/admin/system-info')}>
                  <UserRound className="mr-2 h-4 w-4" />
                  Thông số hệ thống
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/change-password')}>
                  <KeyRound className="mr-2 h-4 w-4" />
                  Đổi mật khẩu
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={handleLogout}
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  Đăng xuất
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {!collapsed && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 text-sidebar-muted hover:text-sidebar-foreground hover:bg-sidebar-accent"
                title="Cài đặt tài khoản"
                aria-label="Cài đặt tài khoản"
                onClick={() => navigate('/change-password')}
              >
                <Settings2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </aside>

      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">

        <header className="flex h-14 shrink-0 items-center border-b bg-card/80 px-4 gap-2 backdrop-blur supports-[backdrop-filter]:bg-card/70">
          <MobileNavigation items={flatNavItems} pathname={location.pathname} title="LMS FaceID Admin" />
          <AppBreadcrumb items={breadcrumbs} className="hidden md:flex" />
          <div className="flex-1" />
          <span className="hidden md:block text-sm text-muted-foreground truncate max-w-[140px]">{user?.username}</span>
          <NotificationBell />
          <ModeToggle />
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-screen-2xl p-4 md:p-6 lg:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

export default AdminLayout
