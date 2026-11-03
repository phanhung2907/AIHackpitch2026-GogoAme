import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ShoppingCart } from 'lucide-react'
import { api } from '../../api/client'
import { cartSchema, firstIssue, noteSchema } from '../../api/schemas'
import { ApiError, type MenuItem } from '../../api/types'
import { useCart } from '../../stores/cart'
import { Button, Card, Empty, ErrorBox, vnd } from '../../lib/ui'

/** /t/:qrToken — QR của bàn mở ra đúng menu của bàn đó, khách không cần đăng nhập. */
export function MenuPage() {
  const { qrToken = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const cart = useCart()
  const [category, setCategory] = useState<string>('Tất cả')
  const [cartOpen, setCartOpen] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const boot = useQuery({
    queryKey: ['guest', 'bootstrap', qrToken],
    queryFn: () => api.guestBootstrap(qrToken),
    retry: false,
  })
  const menu = useQuery({ queryKey: ['guest', 'menu'], queryFn: api.menu, refetchInterval: 3000 })
  const recos = useQuery({ queryKey: ['guest', 'recommendations'], queryFn: api.recommendations, staleTime: 60000 })

  const submit = useMutation({
    mutationFn: () => {
      // Zod validate trước khi gửi; server vẫn validate lại (plan §9.1).
      const lines = cartSchema.parse(
        cart.lines.map((l) => ({
          menu_item_id: l.menu_item_id,
          quantity: l.quantity,
          note: l.note,
          expected_unit_price_vnd: l.unit_price_vnd,
        })),
      )
      return api.submitOrder(qrToken, lines)
    },
    onSuccess: (res) => {
      cart.clear()
      setCartOpen(false)
      setSubmitError(null)
      qc.invalidateQueries()
      navigate(`/guest/bills/${res.bill_id}`)
    },
    // D03/D04: lỗi cả lượt thì giữ nguyên giỏ để khách sửa rồi gửi lại.
    onError: (e) => setSubmitError(firstIssue(e) ?? (e instanceof ApiError ? e.message : 'Gửi order thất bại.')),
  })

  const categories = useMemo(() => {
    const items = menu.data ?? []
    return ['Tất cả', ...new Set(items.map((i) => i.category))]
  }, [menu.data])

  if (boot.isLoading) return <p className="p-6 text-sm text-slate-500">Đang mở bàn…</p>
  if (boot.isError) {
    return (
      <div className="p-6">
        <ErrorBox message="Mã QR không hợp lệ. Vui lòng hỏi nhân viên." />
      </div>
    )
  }

  const items = (menu.data ?? []).filter((i) => category === 'Tất cả' || i.category === category)

  return (
    <div className="mx-auto min-h-screen w-full max-w-md bg-slate-50 pb-28">
      <header className="sticky top-0 z-10 bg-amber-600 px-4 py-3 text-white">
        <p className="text-xs uppercase tracking-wide opacity-80">TapOrder</p>
        <h1 className="text-lg font-bold">Bàn {boot.data?.table_number}</h1>
        {boot.data?.current_bill_id && (
          <Link to={`/guest/bills/${boot.data.current_bill_id}`} className="text-xs underline">
            Xem hóa đơn đang mở của bàn
          </Link>
        )}
      </header>

      <div className="flex gap-2 overflow-x-auto px-4 py-3">
        {categories.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={
              'whitespace-nowrap rounded-full px-3 py-1.5 text-sm ' +
              (c === category ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 border border-slate-200')
            }
          >
            {c}
          </button>
        ))}
      </div>

      {/* F11: gợi ý theo giờ quán, chỉ hiện ở nhóm "Tất cả", không tự thêm vào giỏ. */}
      {category === 'Tất cả' && (recos.data ?? []).length > 0 && (
        <div className="px-4 pb-3">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">Quán gợi ý cho bạn</h2>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {recos.data!.map((r) => (
              <div key={r.item.id} className="w-40 shrink-0 rounded-xl border border-amber-200 bg-amber-50 p-3">
                <p className="truncate font-semibold">{r.item.name}</p>
                <p className="text-xs text-slate-600">{vnd(r.item.unit_price_vnd)}</p>
                <p className="mt-1 text-[11px] text-amber-700">{r.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-3 px-4">
        {menu.isLoading && <p className="text-sm text-slate-500">Đang tải menu…</p>}
        {!menu.isLoading && items.length === 0 && <Empty>Chưa có món trong nhóm này.</Empty>}
        {items.map((item) => (
          <MenuRow key={item.id} item={item} />
        ))}
      </div>

      {cart.count() > 0 && (
        <button
          onClick={() => setCartOpen(true)}
          className="fixed bottom-4 left-1/2 flex w-[calc(100%-2rem)] max-w-md -translate-x-1/2 items-center justify-between rounded-xl bg-slate-900 px-5 py-4 text-white shadow-lg"
        >
          <span className="flex items-center gap-2 text-sm font-medium">
            <ShoppingCart size={18} /> {cart.count()} món
          </span>
          <span className="font-bold">{vnd(cart.total())}</span>
        </button>
      )}

      {cartOpen && (
        <div className="fixed inset-0 z-20 flex items-end bg-black/40" onClick={() => setCartOpen(false)}>
          <div className="max-h-[80vh] w-full overflow-y-auto rounded-t-2xl bg-white p-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-3 text-lg font-bold">Giỏ của bạn</h2>
            {submitError && <div className="mb-3"><ErrorBox message={submitError} /></div>}
            <div className="space-y-3">
              {cart.lines.map((l) => (
                <div key={l.menu_item_id + l.note} className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium">{l.name}</p>
                    {l.note && <p className="truncate text-xs text-slate-500">Ghi chú: {l.note}</p>}
                    <p className="text-xs text-slate-500">{vnd(l.unit_price_vnd)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="secondary" className="px-3" onClick={() => cart.setQuantity(l.menu_item_id, l.note, l.quantity - 1)}>
                      −
                    </Button>
                    <span className="w-6 text-center">{l.quantity}</span>
                    <Button variant="secondary" className="px-3" onClick={() => cart.setQuantity(l.menu_item_id, l.note, l.quantity + 1)}>
                      +
                    </Button>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center justify-between border-t pt-3">
              <span className="text-sm text-slate-500">Tạm tính</span>
              <span className="text-lg font-bold">{vnd(cart.total())}</span>
            </div>
            <Button className="mt-3 w-full" disabled={submit.isPending} onClick={() => submit.mutate()}>
              {submit.isPending ? 'Đang gửi…' : 'Gửi order'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function MenuRow({ item }: { item: MenuItem }) {
  const cart = useCart()
  const [note, setNote] = useState('')
  const [open, setOpen] = useState(false)

  return (
    <Card className={item.available ? '' : 'opacity-60'}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold">{item.name}</p>
          <p className="text-sm text-slate-500">{vnd(item.unit_price_vnd)}</p>
          {!item.available && <p className="mt-1 text-xs font-semibold text-red-600">Hết hàng</p>}
        </div>
        <Button variant="secondary" disabled={!item.available} onClick={() => setOpen((v) => !v)}>
          Thêm
        </Button>
      </div>
      {open && item.available && (
        <div className="mt-3 border-t pt-3">
          <label className="block text-xs font-medium text-slate-600" htmlFor={`note-${item.id}`}>
            Ghi chú (tối đa 250 ký tự)
          </label>
          <input
            id={`note-${item.id}`}
            value={note}
            maxLength={250}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Ít đá, ít ngọt…"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <Button
            className="mt-2 w-full"
            onClick={() => {
              cart.add(item, 1, note.trim())
              setNote('')
              setOpen(false)
            }}
          >
            Thêm vào giỏ
          </Button>
        </div>
      )}
    </Card>
  )
}
