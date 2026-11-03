import { create } from 'zustand'
import type { Staff } from '../api/types'

const KEY = 'taporder.staff'

/**
 * Chỉ để điều hướng UI. Backend thật cưỡng chế quyền bằng cookie session, nên khi
 * VITE_USE_MOCK=0 chỗ này sẽ được thay bằng GET /auth/session. Dùng sessionStorage
 * (không localStorage) để mỗi cửa sổ staff giữ phiên riêng qua reload, đúng yêu cầu
 * "hai profile staff riêng" trong DEMO.txt, và không lưu password.
 */
function restore(): Staff | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Staff) : null
  } catch {
    return null
  }
}

interface StaffState {
  staff: Staff | null
  setStaff: (s: Staff | null) => void
}

export const useStaff = create<StaffState>((set) => ({
  staff: restore(),
  setStaff: (staff) => {
    try {
      if (staff) sessionStorage.setItem(KEY, JSON.stringify(staff))
      else sessionStorage.removeItem(KEY)
    } catch {
      // chặn storage thì vẫn giữ phiên trong memory
    }
    set({ staff })
  },
}))
