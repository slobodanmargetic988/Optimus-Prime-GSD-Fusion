import { createPortal } from 'react-dom'
import type { KeyboardEvent, MouseEvent } from 'react'

import type { CapturePoint } from './types'

interface SelectionBox {
  left: number
  top: number
  width: number
  height: number
}

interface CaptureOverlayProps {
  isCapturing: boolean
  selectionStart: CapturePoint | null
  selectionEnd: CapturePoint | null
  isDragging: boolean
  statusLine: string
  helperHint?: string
  overlayRef: (node: HTMLDivElement | null) => void
  selectionBox: SelectionBox | null
  onMouseDown: (event: MouseEvent<HTMLDivElement>) => void
  onMouseMove: (event: MouseEvent<HTMLDivElement>) => void
  onMouseUp: (event: MouseEvent<HTMLDivElement>) => void
  onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void
  onCancel: () => void
}

export function CaptureOverlay({
  isCapturing,
  selectionStart,
  selectionEnd,
  isDragging,
  statusLine,
  helperHint = 'Click a container or drag a region. The helper note will not appear in the PDF.',
  overlayRef,
  selectionBox,
  onMouseDown,
  onMouseMove,
  onMouseUp,
  onKeyDown,
  onCancel,
}: CaptureOverlayProps) {
  if (!isCapturing) {
    return null
  }

  return createPortal(
    <div
      ref={overlayRef}
      className="capture-overlay"
      data-capture="camera-tool-overlay"
      tabIndex={-1}
      role="presentation"
      onKeyDown={onKeyDown}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
    >
      <div
        className="capture-overlay__hud"
        onMouseDown={(event) => event.stopPropagation()}
        onMouseMove={(event) => event.stopPropagation()}
        onMouseUp={(event) => event.stopPropagation()}
      >
        <p className="capture-overlay__title">{statusLine}</p>
        <p className="capture-overlay__hint">{helperHint}</p>
        <button
          type="button"
          className="capture-overlay__cancel"
          onMouseDown={(event) => event.stopPropagation()}
          onClick={onCancel}
        >
          Exit capture mode
        </button>
      </div>

      {selectionBox && selectionStart && selectionEnd ? (
        <div
          className={isDragging ? 'capture-overlay__selection capture-overlay__selection--dragging' : 'capture-overlay__selection'}
          style={{
            left: selectionBox.left,
            top: selectionBox.top,
            width: selectionBox.width,
            height: selectionBox.height,
          }}
        >
          <span className="capture-overlay__selection-label">
            {Math.round(selectionBox.width)} x {Math.round(selectionBox.height)} px
          </span>
        </div>
      ) : null}
    </div>,
    document.body,
  )
}
