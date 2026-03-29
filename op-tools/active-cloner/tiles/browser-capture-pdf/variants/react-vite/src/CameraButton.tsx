import { useEffect, useRef } from 'react'

interface CaptureCameraButtonProps {
  isActive: boolean
  statusLine: string
  onSingleClick: () => void
  onDoubleClick: () => void
}

function CameraGlyph() {
  return (
    <svg className="camera-button__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M7.5 6.5h2.25l1.1-1.75h2.8l1.1 1.75H17a2.5 2.5 0 0 1 2.5 2.5v6.5A2.5 2.5 0 0 1 17 18H7a2.5 2.5 0 0 1-2.5-2.5V9A2.5 2.5 0 0 1 7 6.5Z" />
      <circle cx="12" cy="12" r="3.5" />
    </svg>
  )
}

export function CaptureCameraButton({
  isActive,
  statusLine,
  onSingleClick,
  onDoubleClick,
}: CaptureCameraButtonProps) {
  const clickTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (clickTimerRef.current !== null) {
        window.clearTimeout(clickTimerRef.current)
      }
    }
  }, [])

  function clearClickTimer() {
    if (clickTimerRef.current !== null) {
      window.clearTimeout(clickTimerRef.current)
      clickTimerRef.current = null
    }
  }

  function handleClick() {
    clearClickTimer()
    clickTimerRef.current = window.setTimeout(() => {
      onSingleClick()
      clickTimerRef.current = null
    }, 220)
  }

  function handleDoubleClick() {
    clearClickTimer()
    onDoubleClick()
  }

  return (
    <button
      type="button"
      className={isActive ? 'camera-button camera-button--active' : 'camera-button'}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      aria-pressed={isActive}
      title="Single click or Ctrl+Shift+P to enter capture mode. Double click to export the full page."
    >
      <CameraGlyph />
      <span className="camera-button__copy">
        <strong>Camera tool</strong>
        <span>{statusLine}</span>
      </span>
    </button>
  )
}
