import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Lock, User } from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '../auth/AuthContext'
import api from '../api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { ModeToggle } from '@/components/theme-toggle'

const loginSchema = z.object({
  username: z.string().min(1, 'Vui lòng nhập tên đăng nhập'),
  password: z.string().min(1, 'Vui lòng nhập mật khẩu'),
})

type LoginForm = z.infer<typeof loginSchema>

export const LoginPage = () => {
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: { pathname?: string } })?.from?.pathname

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (values: LoginForm) => {
    setLoading(true)
    try {
      const res = await api.post('/auth/login', values)
      const { access_token, user } = res.data
      login(access_token, user)
      toast.success('Đăng nhập thành công!')

      if (user.must_change_password) {
        navigate('/change-password')
      } else {
        navigate(from?.startsWith(`/${user.role}/`) ? from : `/${user.role}/dashboard`)
      }
    } catch (error: unknown) {
      const errMsg =
        (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ||
        'Đăng nhập thất bại. Kiểm tra lại thông tin!'
      toast.error(errMsg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      {/* Theme toggle ở góc trên phải */}
      <div className="absolute top-4 right-4">
        <ModeToggle />
      </div>

      <Card className="w-full max-w-sm shadow-lg">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-2">
            <div className="rounded-full bg-primary/10 p-3">
              <Lock className="h-6 w-6 text-primary" />
            </div>
          </div>
          <CardTitle className="text-2xl">Hệ thống LMS FaceID</CardTitle>
          <CardDescription>Đăng nhập tài khoản</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Tên đăng nhập</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="username"
                  placeholder="Tên đăng nhập / Mã SV / Mã GV"
                  className="pl-9"
                  {...register('username')}
                />
              </div>
              {errors.username && (
                <p className="text-xs text-destructive">{errors.username.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Mật khẩu</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  placeholder="Mật khẩu"
                  className="pl-9"
                  {...register('password')}
                />
              </div>
              {errors.password && (
                <p className="text-xs text-destructive">{errors.password.message}</p>
              )}
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

export default LoginPage
