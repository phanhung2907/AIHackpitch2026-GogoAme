import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { ApiError } from '../../api/types'
import { Button, Card, ErrorBox } from '../../lib/ui'
import { useStaff } from '../../stores/staff'

/** /staff/login — không có role selector; role do server trả về. */
export function StaffLoginPage() {
  const navigate = useNavigate()
  const setStaff = useStaff((s) => s.setStaff)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const login = useMutation({
    mutationFn: () => api.login(username, password),
    onSuccess: (staff) => {
      setStaff(staff)
      navigate(staff.role === 'barista' ? '/staff/kitchen' : '/staff/cashier')
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Đăng nhập thất bại.'),
  })

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <Card className="w-full max-w-sm">
        <h1 className="text-xl font-bold">TapOrder · Nhân viên</h1>
        <p className="mb-4 text-sm text-slate-500">Pha chế và thu ngân dùng tài khoản riêng.</p>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            setError(null)
            login.mutate()
          }}
        >
          <div>
            <label className="block text-sm font-medium" htmlFor="username">
              Tài khoản
            </label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium" htmlFor="password">
              Mật khẩu
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </div>
          {error && <ErrorBox message={error} />}
          <Button type="submit" className="w-full" disabled={login.isPending}>
            {login.isPending ? 'Đang đăng nhập…' : 'Đăng nhập'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
