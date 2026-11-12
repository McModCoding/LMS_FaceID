import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Lock, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '../auth/AuthContext'
import api from '../api/client'
import { Token } from '../types/user'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ModeToggle } from '@/components/theme-toggle'

const schema = z
  .object({
    current_password: z.string().min(1, 'Vui lòng nhập mật khẩu hiện tại'),
    new_password: z
      .string()
      .min(8, 'Mật khẩu mới phải có ít nhất 8 ký tự')
      .regex(/[a-zA-Z]/, 'Mật khẩu mới phải chứa ít nhất 1 chữ cái')
      .regex(/\d/, 'Mật khẩu mới phải chứa ít nhất 1 chữ số'),
    confirm_password: z.string().min(1, 'Vui lòng xác nhận mật khẩu mới'),
  })
  .refine((d) => d.new_password !== d.current_password, {
    message: 'Mật khẩu mới không được trùng với mật khẩu hiện tại',
    path: ['new_password'],
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: 'Mật khẩu xác nhận không khớp',
    path: ['confirm_password'],
  })

type FormValues = z.infer<typeof schema>

export const ForceChangePasswordPage = () => {
  const [loading, setLoading] = useState(false)
  const { user, updateUser } = useAuth()
  const navigate = useNavigate()

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: FormValues) => {
    setLoading(true)
    try {
      const res = await api.post<Token>('/auth/change-password', {
        old_password: values.current_password,
        new_password: values.new_password,
      })

      if (res.data.access_token) {
        localStorage.setItem('token', res.data.access_token)
      }
      if (res.data.refresh_token) {
        localStorage.setItem('refresh_token', res.data.refresh_token)
      }

      if (res.data.user) {
        updateUser(res.data.user)
      } else {
        updateUser({ must_change_password: false })
      }

      toast.success('Đổi mật khẩu thành công!')

      const userRole = res.data.user?.role || user?.role
      if (userRole === 'admin') navigate('/admin/classes')
      else if (userRole === 'lecturer') navigate('/lecturer/dashboard')
      else navigate('/student/dashboard')
    } catch (error: unknown) {
      const data = (error as any)?.response?.data
      const msg =
        data?.detail?.message ||
        data?.error?.message ||
        (typeof data?.detail === 'string' ? data.detail : null) ||
        'Đổi mật khẩu thất bại. Vui lòng kiểm tra lại!'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="absolute top-4 right-4">
        <ModeToggle />
      </div>

      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-2">
            <div className="rounded-full bg-primary/10 p-3">
              <Lock className="h-6 w-6 text-primary" />
            </div>
          </div>
          <CardTitle className="text-xl">Đổi mật khẩu lần đầu</CardTitle>
          <CardDescription>
            Tài khoản của bạn cần đổi mật khẩu trước khi tiếp tục sử dụng hệ thống.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="warning">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Yêu cầu mật khẩu</AlertTitle>
            <AlertDescription>
              Mật khẩu mới phải có tối thiểu 8 ký tự, bao gồm cả chữ cái và chữ số, và khác mật khẩu hiện tại.
            </AlertDescription>
          </Alert>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label>Mật khẩu hiện tại</Label>
              <Input type="password" placeholder="Nhập mật khẩu hiện tại" {...register('current_password')} />
              {errors.current_password && (
                <p className="text-xs text-destructive">{errors.current_password.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Mật khẩu mới</Label>
              <Input type="password" placeholder="Nhập mật khẩu mới (≥ 8 ký tự, chữ và số)" {...register('new_password')} />
              {errors.new_password && (
                <p className="text-xs text-destructive">{errors.new_password.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Xác nhận mật khẩu mới</Label>
              <Input type="password" placeholder="Xác nhận mật khẩu mới" {...register('confirm_password')} />
              {errors.confirm_password && (
                <p className="text-xs text-destructive">{errors.confirm_password.message}</p>
              )}
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Đang xử lý...' : 'Xác nhận đổi mật khẩu'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

export default ForceChangePasswordPage
