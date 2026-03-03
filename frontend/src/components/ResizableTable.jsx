import React, { useState, useCallback, useRef, useEffect } from 'react'

export function ResizableTh({ children, minWidth = 60, className = '', style = {}, ...rest }) {
  const thRef = useRef(null)
  const startX = useRef(0)
  const startW = useRef(0)

  const onMouseDown = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    startX.current = e.clientX
    startW.current = thRef.current?.offsetWidth || 100

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const onMouseMove = (ev) => {
      const newW = Math.max(minWidth, startW.current + (ev.clientX - startX.current))
      if (thRef.current) thRef.current.style.width = newW + 'px'
    }
    const onMouseUp = () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }, [minWidth])

  return (
    <th
      ref={thRef}
      className={`relative ${className}`}
      style={{ ...style, minWidth }}
      {...rest}
    >
      {children}
      <div
        onMouseDown={onMouseDown}
        className="absolute right-0 top-0 h-full w-2 cursor-col-resize hover:bg-indigo-400/40 active:bg-indigo-500/60"
        style={{ zIndex: 2 }}
      />
    </th>
  )
}
