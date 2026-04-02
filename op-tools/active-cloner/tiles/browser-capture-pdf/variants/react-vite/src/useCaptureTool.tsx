import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react'

import { captureArea, captureElement, resolveCaptureTargetFromPoint } from './captureUtils'
import type { CapturePoint, CaptureToolOptions } from './types'

const CAPTURE_CLICK_DELAY_MS = 220
const CAPTURE_DRAG_THRESHOLD_PX = 6
const DEFAULT_FILE_NAME = 'capture.pdf'
const DEFAULT_READY_STATUS = 'Camera tool ready. Single click or Ctrl+Shift+P enters selection mode. Double click exports the full page as PDF.'

interface SelectionBox {
  left: number
  top: number
  width: number
  height: number
}

function buildSelectionBox(start: CapturePoint, end: CapturePoint): SelectionBox {
  return {
    left: Math.min(start.x, end.x),
    top: Math.min(start.y, end.y),
    width: Math.max(Math.abs(end.x - start.x), 1),
    height: Math.max(Math.abs(end.y - start.y), 1),
  }
}

function formatCaptureCoordinates(rect: SelectionBox) {
  return `${Math.round(rect.width)} x ${Math.round(rect.height)} px at ${Math.round(rect.left)}, ${Math.round(rect.top)}`
}

export interface UseCaptureToolResult {
  isCapturing: boolean
  selectionStart: CapturePoint | null
  selectionEnd: CapturePoint | null
  isDragging: boolean
  statusLine: string
  overlayRef: (node: HTMLDivElement | null) => void
  selectionBox: SelectionBox | null
  beginCaptureMode: () => void
  cancelCaptureMode: (message?: string) => void
  handleOverlayMouseDown: (event: MouseEvent<HTMLDivElement>) => void
  handleOverlayMouseMove: (event: MouseEvent<HTMLDivElement>) => void
  handleOverlayMouseUp: (event: MouseEvent<HTMLDivElement>) => void
  handleOverlayKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void
  captureFullPage: () => Promise<void>
}

export function useCaptureTool(options: CaptureToolOptions = {}): UseCaptureToolResult {
  const { fileName = DEFAULT_FILE_NAME, captureTargetSelectors, onStatusChange } = options
  const [isCapturing, setIsCapturing] = useState(false)
  const [selectionStart, setSelectionStart] = useState<CapturePoint | null>(null)
  const [selectionEnd, setSelectionEnd] = useState<CapturePoint | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [statusLine, setStatusLine] = useState(DEFAULT_READY_STATUS)

  const overlayRef = useRef<HTMLDivElement | null>(null)
  const singleClickTimerRef = useRef<number | null>(null)
  const activeCaptureRef = useRef(false)

  const updateStatus = useCallback(
    (message: string) => {
      setStatusLine(message)
      onStatusChange?.(message)
    },
    [onStatusChange],
  )

  const clearSingleClickTimer = useCallback(() => {
    if (singleClickTimerRef.current !== null) {
      window.clearTimeout(singleClickTimerRef.current)
      singleClickTimerRef.current = null
    }
  }, [])

  const resetSelection = useCallback(() => {
    setSelectionStart(null)
    setSelectionEnd(null)
    setIsDragging(false)
  }, [])

  const cancelCaptureMode = useCallback(
    (message = 'Capture mode cancelled. Camera tool is ready again.') => {
      clearSingleClickTimer()
      activeCaptureRef.current = false
      setIsCapturing(false)
      resetSelection()
      updateStatus(message)
    },
    [clearSingleClickTimer, resetSelection, updateStatus],
  )

  const beginCaptureMode = useCallback(() => {
    activeCaptureRef.current = true
    setIsCapturing(true)
    resetSelection()
    updateStatus('Capture mode active. The helper panel stays outside the capture and will not appear in the PDF. Click a container or drag a region. Press Escape to exit.')
  }, [resetSelection, updateStatus])

  const finishCapture = useCallback(
    (message: string) => {
      activeCaptureRef.current = false
      setIsCapturing(false)
      resetSelection()
      updateStatus(message)
    },
    [resetSelection, updateStatus],
  )

  const captureFullPage = useCallback(async () => {
    clearSingleClickTimer()
    activeCaptureRef.current = false
    setIsCapturing(false)
    resetSelection()
    updateStatus(`Exporting the full page as ${fileName}.`)

    try {
      await captureElement(document.body, fileName)
      updateStatus(`Full page PDF exported as ${fileName}.`)
    } catch (error) {
      updateStatus(
        error instanceof Error
          ? `Full page capture failed: ${error.message}`
          : 'Full page capture failed for an unknown reason.',
      )
    }
  }, [clearSingleClickTimer, fileName, resetSelection, updateStatus])

  const handleOverlayMouseDown = useCallback((event: MouseEvent<HTMLDivElement>) => {
    if (!activeCaptureRef.current || event.button !== 0) {
      return
    }

    event.preventDefault()
    const point = { x: event.clientX, y: event.clientY }
    setSelectionStart(point)
    setSelectionEnd(point)
    setIsDragging(false)
    updateStatus('Drag to export a region, or release to export the clicked container.')
  }, [updateStatus])

  const handleOverlayMouseMove = useCallback((event: MouseEvent<HTMLDivElement>) => {
    if (!activeCaptureRef.current || selectionStart === null) {
      return
    }

    event.preventDefault()
    const point = { x: event.clientX, y: event.clientY }
    setSelectionEnd(point)

    const box = buildSelectionBox(selectionStart, point)
    if (box.width > CAPTURE_DRAG_THRESHOLD_PX || box.height > CAPTURE_DRAG_THRESHOLD_PX) {
      setIsDragging(true)
      updateStatus(`Region selection active: ${formatCaptureCoordinates(box)}.`)
    }
  }, [selectionStart, updateStatus])

  const handleOverlayMouseUp = useCallback(async (event: MouseEvent<HTMLDivElement>) => {
    if (!activeCaptureRef.current || event.button !== 0 || selectionStart === null) {
      return
    }

    event.preventDefault()

    const endPoint = selectionEnd ?? { x: event.clientX, y: event.clientY }
    const box = buildSelectionBox(selectionStart, endPoint)
    const isDragSelection = isDragging || box.width > CAPTURE_DRAG_THRESHOLD_PX || box.height > CAPTURE_DRAG_THRESHOLD_PX

    try {
      if (isDragSelection) {
        const pageRect = {
          x: box.left + window.scrollX,
          y: box.top + window.scrollY,
          width: box.width,
          height: box.height,
        }

        updateStatus(`Exporting selected region: ${formatCaptureCoordinates(box)}.`)
        await captureArea(pageRect, fileName)
        finishCapture(`Selected region exported as ${fileName}.`)
        return
      }

      const target = resolveCaptureTargetFromPoint(
        event.clientX,
        event.clientY,
        overlayRef.current,
        captureTargetSelectors,
      )
      if (!target) {
        finishCapture('No capture target was found. Camera tool closed without export.')
        return
      }

      updateStatus(`Exporting ${target.tagName.toLowerCase()} as ${fileName}.`)
      await captureElement(target, fileName)
      finishCapture(`Captured ${target.tagName.toLowerCase()} as ${fileName}.`)
    } catch (error) {
      finishCapture(
        error instanceof Error
          ? `Capture failed: ${error.message}`
          : 'Capture failed for an unknown reason.',
      )
    }
  }, [captureTargetSelectors, fileName, finishCapture, isDragging, selectionEnd, selectionStart, updateStatus])

  const handleOverlayKeyDown = useCallback((event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      cancelCaptureMode()
    }
  }, [cancelCaptureMode])

  const selectionBox = useMemo(() => {
    if (selectionStart === null || selectionEnd === null) {
      return null
    }
    return buildSelectionBox(selectionStart, selectionEnd)
  }, [selectionEnd, selectionStart])

  useEffect(() => {
    const body = document.body
    const previousCursor = body.style.cursor
    const previousUserSelect = body.style.userSelect
    const bodyStyle = body.style as CSSStyleDeclaration & { webkitUserSelect?: string }
    const previousWebkitUserSelect = bodyStyle.webkitUserSelect

    if (isCapturing) {
      body.style.cursor = 'crosshair'
      body.style.userSelect = 'none'
      bodyStyle.webkitUserSelect = 'none'
    } else {
      body.style.cursor = previousCursor
      body.style.userSelect = previousUserSelect
      bodyStyle.webkitUserSelect = previousWebkitUserSelect
    }

    return () => {
      body.style.cursor = previousCursor
      body.style.userSelect = previousUserSelect
      bodyStyle.webkitUserSelect = previousWebkitUserSelect
    }
  }, [isCapturing])

  useEffect(() => {
    if (!isCapturing) {
      return undefined
    }

    function handleWindowKeyDown(event: globalThis.KeyboardEvent) {
      const isShortcut = event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'p'

      if (isShortcut) {
        event.preventDefault()
        if (activeCaptureRef.current) {
          void captureFullPage()
        } else {
          beginCaptureMode()
        }
        return
      }

      if (event.key === 'Escape') {
        event.preventDefault()
        cancelCaptureMode()
      }
    }

    window.addEventListener('keydown', handleWindowKeyDown)
    return () => window.removeEventListener('keydown', handleWindowKeyDown)
  }, [beginCaptureMode, cancelCaptureMode, captureFullPage, isCapturing])

  useEffect(() => {
    function handleGlobalCaptureShortcut(event: globalThis.KeyboardEvent) {
      const isShortcut = event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'p'
      if (!isShortcut || activeCaptureRef.current) {
        return
      }

      const target = event.target
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        (target instanceof HTMLElement && target.isContentEditable)
      ) {
        event.preventDefault()
        beginCaptureMode()
        return
      }

      event.preventDefault()
      beginCaptureMode()
    }

    window.addEventListener('keydown', handleGlobalCaptureShortcut)
    return () => window.removeEventListener('keydown', handleGlobalCaptureShortcut)
  }, [beginCaptureMode])

  useEffect(() => {
    return () => clearSingleClickTimer()
  }, [clearSingleClickTimer])

  const handleCameraSingleClick = useCallback(() => {
    clearSingleClickTimer()
    singleClickTimerRef.current = window.setTimeout(() => {
      beginCaptureMode()
      singleClickTimerRef.current = null
    }, CAPTURE_CLICK_DELAY_MS)
  }, [beginCaptureMode, clearSingleClickTimer])

  return {
    isCapturing,
    selectionStart,
    selectionEnd,
    isDragging,
    statusLine,
    overlayRef: useCallback((node: HTMLDivElement | null) => {
      overlayRef.current = node
    }, []),
    selectionBox,
    beginCaptureMode: handleCameraSingleClick,
    cancelCaptureMode,
    handleOverlayMouseDown,
    handleOverlayMouseMove,
    handleOverlayMouseUp,
    handleOverlayKeyDown,
    captureFullPage,
  }
}
