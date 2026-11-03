import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '../../api/client'
import { ApiError, type Table } from '../../api/types'
import { Button, Card, Empty, ErrorBox, StatusBadge, clock, vnd } from '../../lib/ui'
import { SyncBadge, pollInterval, useOnline } from '../../lib/sync'

/** /staff/cashier — bảng bàn, tổng tiền, điều kiện thu tiền do server tính. */
export function CashierTablesPage() {
  const online = useOnline()
  const tables = useQuery({
    queryKey: ['cashier', 'tables'],
    queryFn: api.tables,
    refetchInterval: pollInterval(online, 2000),
  })
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
        <div className="flex items-center gap-3">
          <SyncBadge updatedAt={tables.dataUpdatedAt} intervalMs={2000} />
          {!shift.data && (
            <Link to="/staff/cashier/shift">
              <Button>Mở ca ngay</Button>
            </Link>
          )}
        </div>
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
    mutationFn: ({ total, version }: { total: number; version: number }) => api.pay(id, total, version),
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
            <Button
              className="mt-3 w-full"
              disabled={!b.can_pay || pay.isPending}
              onClick={() => pay.mutate({ total: b.total_vnd, version: b.version })}
            >
              {pay.isPending ? 'Đang xác nhận…' : 'Xác nhận đã thu tiền mặt'}
            </Button>
            {!b.can_pay && <p className="mt-2 text-xs text-slate-500">Còn món chưa xong hoặc bàn chưa có món.</p>}
          </>
        )}
      </Card>
    </div>
  )
}

/** /staff/cashier/qr — QR từng bàn, xuất PNG để in; SVG là phương án dự phòng (F10). */
export function CashierQrPage() {
  const tables = useQuery({ queryKey: ['cashier', 'tables'], queryFn: api.tables })

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">QR theo bàn</h1>
        <p className="text-sm text-slate-500">
          Mỗi bàn một đường dẫn riêng; quét là vào menu đúng bàn. QR dùng base URL đang chạy.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {(tables.data ?? []).map((t) => (
          <TableQrCard key={t.number} tableNumber={t.number} table={t} />
        ))}
      </div>
    </div>
  )
}

function download(href: string, filename: string) {
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  a.click()
}

function TableQrCard({ tableNumber, table }: { tableNumber: number; table: Table }) {
  const qr = useQuery({ queryKey: ['cashier', 'qr', table.id ?? table.number], queryFn: () => api.tableQr(table) })
  const url = qr.data ?? ''
  const holder = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  function svgElement(): SVGSVGElement | null {
    return holder.current?.querySelector('svg') ?? null
  }

  function saveSvg() {
    const svg = svgElement()
    if (!svg) return setError('Chưa render được QR.')
    const blob = new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml' })
    download(URL.createObjectURL(blob), `table-${tableNumber}.svg`)
  }

  // SVG → canvas → PNG. Nếu canvas lỗi thì rơi về tải SVG thay vì im lặng.
  function savePng() {
    const svg = svgElement()
    if (!svg) return setError('Chưa render được QR.')
    const source = new XMLSerializer().serializeToString(svg)
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = 512
      canvas.height = 512
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        setError('Không xuất được PNG, đã tải SVG thay thế.')
        return saveSvg()
      }
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
      try {
        download(canvas.toDataURL('image/png'), `table-${tableNumber}.png`)
        setError(null)
      } catch {
        setError('Không xuất được PNG, đã tải SVG thay thế.')
        saveSvg()
      }
    }
    img.onerror = () => {
      setError('Không xuất được PNG, đã tải SVG thay thế.')
      saveSvg()
    }
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(source)))
  }

  return (
    <Card className="text-center">
      <p className="font-bold">Bàn {tableNumber}</p>
      <div ref={holder} className="my-3 flex justify-center">
        {url ? <QRCodeSVG value={url} size={160} level="M" includeMargin /> : <p>Đang lấy QR…</p>}
      </div>
      <p className="break-all text-xs text-slate-500">{url}</p>
      {error && <p className="mt-2 text-xs text-amber-700">{error}</p>}
      <div className="mt-2 grid grid-cols-3 gap-2">
        <Button variant="secondary" className="px-2 text-xs" onClick={() => navigator.clipboard?.writeText(url)}>
          Copy
        </Button>
        <Button variant="secondary" className="px-2 text-xs" onClick={savePng}>
          PNG
        </Button>
        <Button variant="secondary" className="px-2 text-xs" onClick={saveSvg}>
          SVG
        </Button>
      </div>
    </Card>
  )
}

/** /staff/cashier/shift — mở/đóng ca và báo cáo doanh thu ca đang mở. */
export function CashierShiftPage() {
  const qc = useQueryClient()
  const shift = useQuery({ queryKey: ['cashier', 'shift'], queryFn: api.shiftCurrent, refetchInterval: 3000 })
  const report = useQuery({
    queryKey: ['cashier', 'report', shift.data?.id ?? null],
    queryFn: () => api.shiftReport(shift.data?.id ?? null),
    refetchInterval: 3000,
  })
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
    mutationFn: ({ id, version }: { id: string; version: number }) => api.closeShift(id, version),
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
            <Button
              variant="danger"
              className="mt-3 w-full"
              disabled={close.isPending}
              onClick={() => close.mutate({ id: shift.data!.id, version: shift.data!.version })}
            >
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
