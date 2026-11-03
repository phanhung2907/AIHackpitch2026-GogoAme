import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api, usingMock } from '../../api/client'
import { useStaff } from '../../stores/staff'
import { Button } from '../../lib/ui'

const LINKS: Record<'barista' | 'cashier', Array<{ to: string; label: string }>> = {
  barista: [
    { to: '/staff/kitchen', label: 'Hàng đợi' },
    { to: '/staff/kitchen/menu', label: 'Còn hàng' },
  ],
  cashier: [
    { to: '/staff/cashier', label: 'Bàn' },
    { to: '/staff/cashier/qr', label: 'QR' },
    { to: '/staff/cashier/shift', label: 'Ca' },
  ],
}

/** Sidebar theo role chỉ là UX; backend thật vẫn chặn ở API. */
export function StaffLayout({ role }: { role: 'barista' | 'cashier' }) {
  const staff = useStaff((s) => s.staff)
  const setStaff = useStaff((s) => s.setStaff)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [restoring, setRestoring] = useState(!usingMock)
  useEffect(() => {
    if (usingMock) return
    let active = true
    api.session().then((s) => { if (active) setStaff(s) }).catch(() => { if (active) { setStaff(null); qc.clear() } }).finally(() => { if (active) setRestoring(false) })
    return () => { active = false }
  }, [setStaff, qc])
  if (restoring) return <p className="p-6">Đang khôi phục phiên…</p>


  if (!staff || staff.role !== role) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-lg font-semibold">Bạn chưa đăng nhập đúng vai trò.</p>
        <Link to="/staff/login" className="text-amber-700 underline">
          Về trang đăng nhập
        </Link>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="flex flex-wrap items-center justify-between gap-3 bg-slate-900 px-4 py-3 text-white">
        <div className="flex items-center gap-4">
          <span className="font-bold">TapOrder</span>
          <nav className="flex gap-1">
            {LINKS[role].map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end
                className={({ isActive }) =>
                  'rounded-lg px-3 py-1.5 text-sm ' + (isActive ? 'bg-white text-slate-900' : 'hover:bg-white/10')
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="opacity-80">
            {staff.username} · {role === 'barista' ? 'Pha chế' : 'Thu ngân'}
          </span>
          <Button
            variant="ghost"
            className="text-white hover:bg-white/10"
            onClick={() => {
              void api.logout()
              qc.clear()
              setStaff(null)
              navigate('/staff/login')
            }}
          >
            Đăng xuất
          </Button>
        </div>
      </header>
      <main className="p-4">
        <Outlet />
      </main>
    </div>
  )
}
