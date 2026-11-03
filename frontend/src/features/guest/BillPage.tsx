import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api, guestId, usingMock } from '../../api/client'
import { ApiError } from '../../api/types'
import { Button, Card, ErrorBox, StatusBadge, clock, vnd } from '../../lib/ui'
import { SyncBadge, pollInterval, useOnline } from '../../lib/sync'

/** /guest/bills/:id — khách theo dõi trạng thái món, hủy món của mình, gọi thêm. */
export function BillPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const me = guestId()

  // Polling thay SSE ở bản mock; mất mạng thì giãn về 5s (plan §3.3).
  const online = useOnline()
  const bill = useQuery({
    queryKey: ['guest', 'bill', id],
    queryFn: () => api.bill(id),
    refetchInterval: pollInterval(online, 2000),
  })

  const cancel = useMutation({
    mutationFn: ({ itemId, version }: { itemId: string; version: number }) => api.cancelItem(itemId, version),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['guest', 'bill', id] }),
  })

  if (bill.isLoading) return <p className="p-6 text-sm text-slate-500">Đang tải hóa đơn…</p>
  if (bill.isError || !bill.data) {
    return (
      <div className="p-6">
        <ErrorBox message="Không xem được hóa đơn này." onRetry={() => bill.refetch()} />
      </div>
    )
  }

  const b = bill.data
  const qrToken = usingMock ? `t${b.table_number}` : sessionStorage.getItem('taporder.qr') ?? ''

  return (
    <div className="mx-auto min-h-screen w-full max-w-md bg-slate-50 pb-24">
      <header className="sticky top-0 z-10 bg-slate-900 px-4 py-3 text-white">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h1 className="text-lg font-bold">Bàn {b.table_number}</h1>
            <p className="text-xs opacity-80">
              {b.status === 'open' ? 'Đang phục vụ' : `Đã thanh toán ${b.paid_at ? clock(b.paid_at) : ''}`}
            </p>
          </div>
          <SyncBadge updatedAt={bill.dataUpdatedAt} intervalMs={2000} />
        </div>
      </header>

      {cancel.isError && (
        <div className="px-4 pt-4">
          <ErrorBox message={cancel.error instanceof ApiError ? cancel.error.message : 'Hủy không thành công.'} />
        </div>
      )}

      <div className="space-y-4 p-4">
        {b.orders.map((order) => (
          <Card key={order.id}>
            <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
              Lượt #{order.order_number} · {clock(order.created_at)}
            </p>
            <div className="space-y-3">
              {order.items.map((item) => (
                <div key={item.id} className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium">
                      {item.quantity}× {item.name}
                    </p>
                    {item.note && <p className="text-xs text-slate-500">Ghi chú: {item.note}</p>}
                    <p className="text-xs text-slate-500">{vnd(item.unit_price_vnd * item.quantity)}</p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <StatusBadge status={item.status} />
                    {/* D01: chỉ dòng của chính phiên khách này và còn chờ mới hủy được. */}
                    {b.status === 'open' && item.status === 'waiting' && (usingMock ? item.guest_id === me : item.can_cancel) && (
                      <Button
                        variant="danger"
                        className="px-3 text-xs"
                        disabled={cancel.isPending}
                        onClick={() => cancel.mutate({ itemId: item.id, version: item.version })}
                      >
                        Hủy món
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>

      <div className="fixed bottom-0 left-1/2 w-full max-w-md -translate-x-1/2 border-t bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm text-slate-500">Tổng cộng</span>
          <span className="text-xl font-bold">{vnd(b.total_vnd)}</span>
        </div>
        {b.status === 'open' ? (
          <Link to={`/t/${qrToken}`}>
            <Button className="w-full">Gọi thêm món</Button>
          </Link>
        ) : (
          // D02: bill đã trả tiền thì tab cũ chỉ còn là biên nhận; QR mở lượt mới.
          <Link to={`/t/${qrToken}`}>
            <Button variant="secondary" className="w-full">
              Bắt đầu lượt mới
            </Button>
          </Link>
        )}
      </div>
    </div>
  )
}
