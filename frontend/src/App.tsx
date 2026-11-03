import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { MenuPage } from './features/guest/MenuPage'
import { BillPage } from './features/guest/BillPage'
import { StaffLoginPage } from './features/auth/StaffLoginPage'
import { StaffLayout } from './components/layout/StaffLayout'
import { KitchenMenuPage, KitchenQueuePage } from './features/kitchen/KitchenPages'
import {
  CashierBillPage,
  CashierQrPage,
  CashierShiftPage,
  CashierTablesPage,
} from './features/cashier/CashierPages'
import { api } from './api/client'
import { Button, Card } from './lib/ui'

/** Trang chỉ dùng khi demo: lối vào nhanh ba vai trò. */
function DemoHome() {
  return (
    <div className="min-h-screen bg-slate-100 p-6">
      <div className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-2xl font-bold">TapOrder — gọi món tại bàn bằng QR</h1>
        <Card>
          <h2 className="font-semibold">Khách (không cần đăng nhập)</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <Link key={n} to={`/t/t${n}`}>
                <Button variant="secondary">Bàn {n}</Button>
              </Link>
            ))}
          </div>
        </Card>
        <Card>
          <h2 className="font-semibold">Nhân viên</h2>
          <p className="text-sm text-slate-500">barista / barista123 · cashier / cashier123</p>
          <Link to="/staff/login">
            <Button className="mt-2">Đăng nhập</Button>
          </Link>
        </Card>
        <Card>
          <h2 className="font-semibold">Dữ liệu demo</h2>
          <p className="text-sm text-slate-500">Xóa toàn bộ bill, payment và ca để chạy lại kịch bản.</p>
          <Button
            variant="danger"
            className="mt-2"
            onClick={() => {
              api.resetDemo()
              window.location.reload()
            }}
          >
            Reset dữ liệu
          </Button>
        </Card>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<DemoHome />} />
      <Route path="/t/:qrToken" element={<MenuPage />} />
      <Route path="/guest/bills/:id" element={<BillPage />} />
      <Route path="/staff/login" element={<StaffLoginPage />} />
      <Route path="/staff/kitchen" element={<StaffLayout role="barista" />}>
        <Route index element={<KitchenQueuePage />} />
        <Route path="menu" element={<KitchenMenuPage />} />
      </Route>
      <Route path="/staff/cashier" element={<StaffLayout role="cashier" />}>
        <Route index element={<CashierTablesPage />} />
        <Route path="bills/:id" element={<CashierBillPage />} />
        <Route path="qr" element={<CashierQrPage />} />
        <Route path="shift" element={<CashierShiftPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
