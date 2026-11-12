import { Fragment, useState, useMemo } from 'react'
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom'
import {
  BookOpen,
  Calendar,
  LayoutDashboard,
  Menu,
  LogOut,
  KeyRound,
  UserRound,
  ChevronRight,
  UserCheck,
  ScanFace,
  FolderOpen,
  Settings,
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

interface NavItem {
  key: string
  label: string
  icon: React.ReactNode
}

const navGroups: { label: string; items: NavItem[] }[] = [
  {
    label: 'Học tập',
    items: [
      { key: '/student/dashboard', label: 'Trang chủ', icon: <LayoutDashboard className="h-4 w-4" /> },
      { key: '/student/classes', label: 'Lớp học của tôi', icon: <BookOpen className="h-4 w-4" /> },
      { key: '/student/documents', label: 'Tài liệu môn học', icon: <FolderOpen className="h-4 w-4" /> },
      { key: '/student/timetable', label: 'Thời khóa biểu', icon: <Calendar className="h-4 w-4" /> },
    ],
  },
  {
    label: 'Tài khoản',
    items: [
      { key: '/student/profile', label: 'Hồ sơ cá nhân', icon: <UserRound className="h-4 w-4" /> },
      { key: '/student/face', label: 'Đăng ký khuôn mặt', icon: <ScanFace className="h-4 w-4" /> },
    ],
  },
]

const navItems: NavItem[] = navGroups.flatMap(g => g.items)

export const StudentLayout = () => {
  const [collapsed, setCollapsed] = useState(false)
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const initials = user?.username ? user.username.slice(0, 2).toUpperCase() : 'SV'

  const breadcrumbs: BreadcrumbItem[] = useMemo(() => {
    const path = location.pathname
    if (path === '/student/dashboard') return [{ label: 'Trang chủ' }]
    if (path === '/student/classes') return [{ label: 'Lớp học của tôi' }]
    if (path.startsWith('/student/classes/')) return [{ label: 'Lớp học của tôi', href: '/student/classes' }, { label: 'Chi tiết lớp' }]
    if (path.startsWith('/student/materials')) return [{ label: 'Học liệu' }]
    if (path.startsWith('/student/documents')) return [{ label: 'Tài liệu môn học' }]
    if (path === '/student/timetable') return [{ label: 'Thời khóa biểu' }]
    if (path === '/student/profile') return [{ label: 'Hồ sơ cá nhân' }]
    if (path === '/student/face') return [{ label: 'Đăng ký khuôn mặt' }]
    if (path.startsWith('/student/exams/')) return [{ label: 'Lớp học của tôi', href: '/student/classes' }, { label: 'Làm bài kiểm tra' }]
    if (path === '/student/notifications') return [{ label: 'Thông báo' }]
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
            <UserCheck className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="ml-2.5 min-w-0">
              <div className="font-semibold text-sm leading-tight text-sidebar-foreground tracking-tight truncate">LMS FaceID</div>
              <div className="text-[11px] text-sidebar-muted truncate">Không gian học tập</div>
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
            {navGroups.map((group) => (
              <Fragment key={group.label}>
                {!collapsed && (
                  <p className="px-2.5 pb-1 pt-3.5 text-[11px] font-semibold uppercase tracking-wider text-sidebar-muted/80">
                    {group.label}
                  </p>
                )}
                {group.items.map((item) => {
                  const active = location.pathname.startsWith(item.key)
                  return (
                    <Link
                      key={item.key}
                      to={item.key}
                      className={cn(
                        'flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-all duration-150',
                        active
                          ? 'bg-primary text-primary-foreground font-semibold shadow-xs'
                          : 'text-sidebar-muted hover:bg-sidebar-accent hover:text-sidebar-foreground'
                      )}
                      title={collapsed ? item.label : undefined}
                    >
                      <span className={cn('shrink-0', active ? 'text-primary-foreground' : 'text-sidebar-muted group-hover:text-sidebar-foreground')}>
                        {item.icon}
                      </span>
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </Link>
                  )
                })}
              </Fragment>
            ))}
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
                      <p className="truncate text-[11px] text-sidebar-muted">Sinh viên</p>
                    </div>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" side="right" className="w-52">
                <DropdownMenuItem onClick={() => navigate('/student/profile')}>
                  <UserRound className="mr-2 h-4 w-4" />
                  Hồ sơ cá nhân
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/change-password')}>
                  <KeyRound className="mr-2 h-4 w-4" />
                  Đổi mật khẩu
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/student/face')}>
                  <ScanFace className="mr-2 h-4 w-4" />
                  Đăng ký khuôn mặt
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
                <Settings className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </aside>

      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">

        <header className="flex h-14 shrink-0 items-center border-b bg-card/80 px-4 gap-2 backdrop-blur supports-[backdrop-filter]:bg-card/70">
          <MobileNavigation items={navItems} pathname={location.pathname} title="Cổng Sinh viên" />
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

export default StudentLayout
