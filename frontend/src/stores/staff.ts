import { create } from 'zustand'
import type { Staff } from '../api/types'

interface StaffState {
  staff: Staff | null
  setStaff: (s: Staff | null) => void
}

/** Chỉ để điều hướng UI. Backend thật vẫn cưỡng chế quyền bằng cookie session. */
export const useStaff = create<StaffState>((set) => ({
  staff: null,
  setStaff: (staff) => set({ staff }),
}))
