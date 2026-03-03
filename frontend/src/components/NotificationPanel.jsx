import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  clearNotifications
} from '../api/client'

const TYPE_STYLES = {
  error:   { bg: 'bg-red-50',    border: 'border-red-400',   icon: '❌', label: 'text-red-700' },
  warning: { bg: 'bg-amber-50',  border: 'border-amber-400', icon: '⚠️', label: 'text-amber-700' },
  success: { bg: 'bg-emerald-50', border: 'border-emerald-400', icon: '✅', label: 'text-emerald-700' },
  info:    { bg: 'bg-blue-50',   border: 'border-blue-400',  icon: 'ℹ️', label: 'text-blue-700' },
}

export default function NotificationPanel() {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [unread, setUnread] = useState(0)
  const panelRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const data = await getNotifications()
      if (data.success) {
        setNotifications(data.notifications || [])
        setUnread(data.unread_count ?? 0)
      }
    } catch (_) {}
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [load])

  useEffect(() => {
    function onClick(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const handleOpen = async () => {
    setOpen((o) => !o)
    if (!open) load()
  }

  const handleMarkAllRead = async () => {
    await markAllNotificationsRead()
    load()
  }

  const handleClear = async () => {
    await clearNotifications()
    load()
  }

  const handleReadOne = async (id) => {
    await markNotificationRead(id)
    load()
  }

  return (
    <div ref={panelRef} className="relative">
      <button
        type="button"
        onClick={handleOpen}
        className="relative rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
        title="Notifications"
      >
        🔔 Notifications
        {unread > 0 && (
          <span className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-[420px] max-h-[520px] flex flex-col rounded-xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <h3 className="text-sm font-semibold text-slate-800">Notifications</h3>
            <div className="flex gap-2">
              {unread > 0 && (
                <button onClick={handleMarkAllRead} className="rounded px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50">
                  Mark all read
                </button>
              )}
              {notifications.length > 0 && (
                <button onClick={handleClear} className="rounded px-2 py-1 text-xs text-red-500 hover:bg-red-50">
                  Clear all
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="py-10 text-center text-sm text-slate-400">No notifications</div>
            ) : (
              notifications.map((n) => {
                const s = TYPE_STYLES[n.type] || TYPE_STYLES.info
                return (
                  <div
                    key={n.id}
                    onClick={() => !n.read && handleReadOne(n.id)}
                    className={`cursor-pointer border-b border-slate-50 px-4 py-3 transition hover:bg-slate-50 ${!n.read ? 'bg-indigo-50/40' : ''}`}
                  >
                    <div className="flex items-start gap-2">
                      <span className="mt-0.5 text-base">{s.icon}</span>
                      <div className="flex-1 min-w-0">
                        <div className={`text-sm font-medium ${s.label}`}>{n.title}</div>
                        <div className="mt-0.5 whitespace-pre-wrap text-xs text-slate-600 leading-relaxed">{n.detail}</div>
                        <div className="mt-1 text-[10px] text-slate-400">
                          {new Date(n.timestamp).toLocaleString()}
                        </div>
                      </div>
                      {!n.read && <span className="mt-1 h-2 w-2 flex-shrink-0 rounded-full bg-indigo-500" />}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
