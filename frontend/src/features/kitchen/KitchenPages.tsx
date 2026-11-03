import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import { ApiError } from '../../api/types'
import { Button, Card, Empty, ErrorBox, StatusBadge, clock } from '../../lib/ui'
import { SyncBadge, pollInterval, useOnline } from '../../lib/sync'

/** /staff/kitchen — hàng đợi FIFO, không hiện giá hay thanh toán (ma trận quyền §4.2). */
export function KitchenQueuePage() {
  const qc = useQueryClient()
  const online = useOnline()
  const queue = useQuery({
    queryKey: ['kitchen', 'queue'],
    queryFn: api.kitchenQueue,
    refetchInterval: pollInterval(online, 2000),
  })
  const advance = useMutation({
    mutationFn: ({ itemId, status, version }: { itemId: string; status: 'preparing' | 'done'; version: number }) =>
      api.setItemStatus(itemId, status, version),
    onSuccess: () => qc.invalidateQueries(),
  })

  const tickets = queue.data ?? []

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold">Hàng đợi pha chế</h1>
          <p className="text-sm text-slate-500">Thứ tự theo thời gian gửi order (FIFO).</p>
        </div>
        <SyncBadge updatedAt={queue.dataUpdatedAt} intervalMs={2000} />
      </div>
      {advance.isError && (
        <ErrorBox message={advance.error instanceof ApiError ? advance.error.message : 'Đổi trạng thái thất bại.'} />
      )}
      {queue.isLoading && <p className="text-sm text-slate-500">Đang tải…</p>}
      {!queue.isLoading && tickets.length === 0 && <Empty>Chưa có món nào cần làm.</Empty>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {tickets.map((t) => (
          <Card key={t.item_id}>
            <div className="flex items-center justify-between">
              <span className="rounded-md bg-slate-900 px-2 py-1 text-xs font-bold text-white">Bàn {t.table_number}</span>
              <StatusBadge status={t.status} />
            </div>
            <p className="mt-3 text-lg font-semibold">
              {t.quantity}× {t.name}
            </p>
            {t.note && <p className="text-sm text-amber-700">Ghi chú: {t.note}</p>}
            <p className="mt-1 text-xs text-slate-500">
              Lượt #{t.order_number} · {clock(t.created_at)}
            </p>
            <div className="mt-3">
              {t.status === 'waiting' ? (
                <Button
                  className="w-full"
                  disabled={advance.isPending}
                  onClick={() => advance.mutate({ itemId: t.item_id, status: 'preparing', version: t.version })}
                >
                  Bắt đầu pha
                </Button>
              ) : (
                <Button
                  className="w-full"
                  disabled={advance.isPending}
                  onClick={() => advance.mutate({ itemId: t.item_id, status: 'done', version: t.version })}
                >
                  Xong
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

/** /staff/kitchen/menu — bật/tắt còn hàng; pha chế không sửa giá. */
export function KitchenMenuPage() {
  const qc = useQueryClient()
  const menu = useQuery({ queryKey: ['kitchen', 'menu'], queryFn: api.kitchenMenu, refetchInterval: 5000 })
  const toggle = useMutation({
    mutationFn: ({ id, available, version }: { id: string; available: boolean; version: number }) =>
      api.setAvailability(id, available, version),
    onSuccess: () => qc.invalidateQueries(),
  })

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">Còn hàng / hết hàng</h1>
        <p className="text-sm text-slate-500">Tắt món là khách không gửi được món đó nữa.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {(menu.data ?? []).map((m) => (
          <Card key={m.id} className="flex items-center justify-between">
            <div>
              <p className="font-medium">{m.name}</p>
              <p className="text-xs text-slate-500">{m.category}</p>
            </div>
            <Button
              variant={m.available ? 'danger' : 'primary'}
              disabled={toggle.isPending}
              onClick={() => toggle.mutate({ id: m.id, available: !m.available, version: m.version })}
            >
              {m.available ? 'Báo hết hàng' : 'Mở bán lại'}
            </Button>
          </Card>
        ))}
      </div>
    </div>
  )
}
