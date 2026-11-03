import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '../../api/client'
import { ApiError } from '../../api/types'
import { Button, Card, Empty, ErrorBox, StatusBadge, clock, vnd } from '../../lib/ui'

/** /staff/cashier — bảng bàn, tổng tiền, điều kiện thu tiền do server tính. */
export function CashierTablesPage() {
  const tables = useQuery({ queryKey: ['cashier', 'tables'], queryFn: api.tables, refetchInterval: 2000 })
  const shift = useQuery({ queryKey: ['cashier', 'shift'], queryFn: api.shiftCurrent, refetchInterval: 5000 })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Bàn đang phục vụ</h1>
          <p className="text-sm text-slate-500">
            {shift.data ? `Ca mở từ ${clock(shift.data.opened_at)}` : 'Chưa mở ca — chưa nhận order được.'}
          </p>
        </div>
        {!shift.data && (
          <Link to="/staff/cashier/shift">
            <Button>Mở ca ngay</Button>
          </Link>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {(tables.data ?? []).map((t) => (
          <Card key={t.number}>
            <div className="flex items-center justify-between">
              <p className="text-lg font-bold">Bàn {t.number}</p>
              <span
                className={
                  'rounded-full px-2.5 py-1 text-xs font-semibold ' +
                  (t.status === 'serving' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600')
                }
              >
                {t.status === 'serving' ? 'Đang phục vụ' : 'Trống'}
              </span>
            </div>
            <p className="mt-3 text-2xl font-bold">{vnd(t.total_vnd)}</p>
            {t.bill_id ? (
              <Link to={`/staff/cashier/bills/${t.bill_id}`}>
                <Button className="mt-3 w-full" variant={t.can_pay ? 'primary' : 'secondary'}>
                  {t.can_pay ? 'Thu tiền' : 'Xem hóa đơn'}
                </Button>
              </Link>
            ) : (
              <p className="mt-3 text-sm text-slate-500">Chưa có hóa đơn mở.</p>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}

/** /staff/cashier/bills/:id — chi tiết và xác nhận tiền mặt. */
export function CashierBillPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const bill = useQuery({ queryKey: ['cashier', 'bill', id], queryFn: () => api.cashierBill(id), refetchInterval: 2000 })
  const pay = useMutation({
    mutationFn: (total: number) => api.pay(id, total),
    onSuccess: () => qc.invalidateQueries(),
  })

  if (bill.isLoading) return <p className="text-sm text-slate-500">Đang tải…</p>
  if (!bill.data) return <ErrorBox message="Không tìm thấy hóa đơn." onRetry={() => bill.refetch()} />

  const b = bill.data
  return (
    <div className="max-w-2xl space-y-4">
      <div>
        <h1 className="text-xl font-bold">Hóa đơn bàn {b.table_number}</h1>
        <p className="text-sm text-slate-500">
          Mở {clock(b.opened_at)} · {b.status === 'paid' ? 'Đã thanh toán' : 'Đang mở'}
        </p>
      </div>

      {pay.isError && <ErrorBox message={pay.error instanceof ApiError ? pay.error.message : 'Thanh toán thất bại.'} />}

      {b.orders.map((order) => (
        <Card key={order.id}>
          <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
            Lượt #{order.order_number} · {clock(order.created_at)}
          </p>
          {order.items.map((item) => (
            <div key={item.id} className="flex items-center justify-between py-1.5">
              <div>
                <p className={item.status === 'cancelled' ? 'text-slate-400 line-through' : 'font-medium'}>
                  {item.quantity}× {item.name}
                </p>
                {item.note && <p className="text-xs text-slate-500">{item.note}</p>}
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={item.status} />
                <span className="w-24 text-right font-medium">
                  {item.status === 'cancelled' ? '—' : vnd(item.unit_price_vnd * item.quantity)}
                </span>
              </div>
            </div>
          ))}
        </Card>
      ))}

      <Card>
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-500">Tổng phải thu</span>
          <span className="text-2xl font-bold">{vnd(b.total_vnd)}</span>
        </div>
        {b.status === 'paid' ? (
          <p className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">
            Đã thu {vnd(b.payment?.amount_vnd ?? b.total_vnd)} tiền mặt lúc {b.paid_at ? clock(b.paid_at) : ''}. Bàn đã đóng.
          </p>
        ) : (
          <>
            {/* D06: chỉ thu khi mọi món chưa hủy đã xong. */}
            <Button className="mt-3 w-full" disabled={!b.can_pay || pay.isPending} onClick={() => pay.mutate(b.total_vnd)}>
              {pay.isPending ? 'Đang xác nhận…' : 'Xác nhận đã thu tiền mặt'}
            </Button>
            {!b.can_pay && <p className="mt-2 text-xs text-slate-500">Còn món chưa xong hoặc bàn chưa có món.</p>}
          </>
        )}
      </Card>
    </div>
  )
}

/** /staff/cashier/qr — QR từng bàn để in dán tại quán. */
export function CashierQrPage() {
  const tables = useQuery({ queryKey: ['cashier', 'tables'], queryFn: api.tables })
  const origin = window.location.origin

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">QR theo bàn</h1>
        <p className="text-sm text-slate-500">Mỗi bàn một đường dẫn riêng; quét là vào menu đúng bàn.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {(tables.data ?? []).map((t) => {
          const url = `${origin}/t/${t.qr_token}`
          return (
            <Card key={t.number} className="text-center">
              <p className="font-bold">Bàn {t.number}</p>
              <div className="my-3 flex justify-center">
                <QRCodeSVG value={url} size={148} />
              </div>
              <p className="break-all text-xs text-slate-500">{url}</p>
              <Button variant="secondary" className="mt-2 w-full" onClick={() => navigator.clipboard?.writeText(url)}>
                Copy link
              </Button>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

/** /staff/cashier/shift — mở/đóng ca và báo cáo doanh thu ca đang mở. */
export function CashierShiftPage() {
  const qc = useQueryClient()
  const shift = useQuery({ queryKey: ['cashier', 'shift'], queryFn: api.shiftCurrent, refetchInterval: 3000 })
  const report = useQuery({ queryKey: ['cashier', 'report'], queryFn: api.shiftReport, refetchInterval: 3000 })
  const [error, setError] = useState<string | null>(null)

  const open = useMutation({
    mutationFn: api.openShift,
    onSuccess: () => {
      setError(null)
      qc.invalidateQueries()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Mở ca thất bại.'),
  })
  const close = useMutation({
    mutationFn: (id: string) => api.closeShift(id),
    onSuccess: () => {
      setError(null)
      qc.invalidateQueries()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Đóng ca thất bại.'),
  })

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-xl font-bold">Ca làm việc</h1>
      {error && <ErrorBox message={error} />}
      <Card>
        {shift.data ? (
          <>
            <p className="text-sm text-slate-500">Ca mở từ {clock(shift.data.opened_at)}</p>
            <Button variant="danger" className="mt-3 w-full" disabled={close.isPending} onClick={() => close.mutate(shift.data!.id)}>
              Đóng ca
            </Button>
          </>
        ) : (
          <>
            <p className="text-sm text-slate-500">Chưa có ca nào đang mở.</p>
            <Button className="mt-3 w-full" disabled={open.isPending} onClick={() => open.mutate()}>
              Mở ca
            </Button>
          </>
        )}
      </Card>

      <Card>
        <h2 className="font-semibold">Doanh thu ca này</h2>
        <p className="mt-2 text-3xl font-bold">{vnd(report.data?.revenue_vnd ?? 0)}</p>
        <p className="text-sm text-slate-500">{report.data?.paid_bill_count ?? 0} hóa đơn đã thu</p>
        <h3 className="mt-4 text-sm font-semibold">Món bán chạy</h3>
        {(report.data?.top_items ?? []).length === 0 ? (
          <Empty>Chưa có hóa đơn nào được thu trong ca.</Empty>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {report.data!.top_items.map((i) => (
              <li key={i.name} className="flex justify-between">
                <span>{i.name}</span>
                <span className="font-medium">{i.quantity}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
