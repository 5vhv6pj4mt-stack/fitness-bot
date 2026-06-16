import { useState, useCallback } from 'react'

export function useToast(duration = 3000) {
  const [toast, setToast] = useState(null)

  const show = useCallback((msg, isError = false) => {
    setToast({ msg, isError })
    setTimeout(() => setToast(null), duration)
  }, [duration])

  const ToastEl = toast
    ? <div className={`toast ${toast.isError ? 'toast-error' : 'toast-ok'}`}>{toast.msg}</div>
    : null

  return { show, ToastEl }
}
