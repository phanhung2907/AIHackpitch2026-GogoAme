import { create } from 'zustand'
import type { MenuItem } from '../api/types'

export interface CartEntry {
  menu_item_id: string
  name: string
  unit_price_vnd: number
  quantity: number
  note: string
}

interface CartState {
  lines: CartEntry[]
  add: (item: MenuItem, quantity: number, note: string) => void
  setQuantity: (menuItemId: string, note: string, quantity: number) => void
  clear: () => void
  total: () => number
  count: () => number
}

/** Giỏ chỉ ở memory; tổng tiền hiển thị là tạm tính, server mới là nguồn chuẩn. */
export const useCart = create<CartState>((set, get) => ({
  lines: [],
  add: (item, quantity, note) =>
    set((s) => {
      const key = (l: CartEntry) => l.menu_item_id === item.id && l.note === note
      const existing = s.lines.find(key)
      if (existing) {
        return { lines: s.lines.map((l) => (key(l) ? { ...l, quantity: l.quantity + quantity } : l)) }
      }
      return {
        lines: [
          ...s.lines,
          { menu_item_id: item.id, name: item.name, unit_price_vnd: item.unit_price_vnd, quantity, note },
        ],
      }
    }),
  setQuantity: (menuItemId, note, quantity) =>
    set((s) => ({
      lines: s.lines
        .map((l) => (l.menu_item_id === menuItemId && l.note === note ? { ...l, quantity } : l))
        .filter((l) => l.quantity > 0),
    })),
  clear: () => set({ lines: [] }),
  total: () => get().lines.reduce((sum, l) => sum + l.unit_price_vnd * l.quantity, 0),
  count: () => get().lines.reduce((sum, l) => sum + l.quantity, 0),
}))
