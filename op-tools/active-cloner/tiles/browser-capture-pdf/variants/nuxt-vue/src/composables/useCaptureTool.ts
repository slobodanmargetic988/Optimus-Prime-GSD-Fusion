import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { captureArea, captureElement, resolveCaptureTargetFromPoint } from '../utils/captureUtils'
import type { CapturePoint, CaptureToolOptions } from '../types'

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

export function useCaptureTool(options: CaptureToolOptions = {}) {
  const { fileName = DEFAULT_FILE_NAME, captureTargetSelectors, onStatusChange } = options

  const isCapturing = ref(false)
  const selectionStart = ref<CapturePoint | null>(null)
  const selectionEnd = ref<CapturePoint | null>(null)
  const isDragging = ref(false)
  const statusLine = ref(DEFAULT_READY_STATUS)
  const overlayElement = ref<HTMLDivElement | null>(null)
  const clickTimer = ref<number | null>(null)
  const activeCapture = ref(false)

  function updateStatus(message: string) {
    statusLine.value = message
    onStatusChange?.(message)
  }

  function clearClickTimer() {
    if (clickTimer.value !== null) {
      window.clearTimeout(clickTimer.value)
      clickTimer.value = null
    }
  }

  function resetSelection() {
    selectionStart.value = null
    selectionEnd.value = null
    isDragging.value = false
  }

  function cancelCaptureMode(message = 'Capture mode cancelled. Camera tool is ready again.') {
    clearClickTimer()
    activeCapture.value = false
    isCapturing.value = false
    resetSelection()
    updateStatus(message)
  }

  function beginCaptureMode() {
    activeCapture.value = true
    isCapturing.value = true
    resetSelection()
    updateStatus('Capture mode active. The helper panel stays outside the capture and will not appear in the PDF. Click a container or drag a region. Press Escape to exit.')
  }

  function finishCapture(message: string) {
    activeCapture.value = false
    isCapturing.value = false
    resetSelection()
    updateStatus(message)
  }

  async function captureFullPage() {
    clearClickTimer()
    activeCapture.value = false
    isCapturing.value = false
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
  }

  function handleOverlayMouseDown(event: MouseEvent) {
    if (!activeCapture.value || event.button !== 0) {
      return
    }

    event.preventDefault()
    const point = { x: event.clientX, y: event.clientY }
    selectionStart.value = point
    selectionEnd.value = point
    isDragging.value = false
    updateStatus('Drag to export a region, or release to export the clicked container.')
  }

  function handleOverlayMouseMove(event: MouseEvent) {
    if (!activeCapture.value || selectionStart.value === null) {
      return
    }

    event.preventDefault()
    const point = { x: event.clientX, y: event.clientY }
    selectionEnd.value = point

    const box = buildSelectionBox(selectionStart.value, point)
    if (box.width > CAPTURE_DRAG_THRESHOLD_PX || box.height > CAPTURE_DRAG_THRESHOLD_PX) {
      isDragging.value = true
      updateStatus(`Region selection active: ${formatCaptureCoordinates(box)}.`)
    }
  }

  async function handleOverlayMouseUp(event: MouseEvent) {
    if (!activeCapture.value || event.button !== 0 || selectionStart.value === null) {
      return
    }

    event.preventDefault()

    const endPoint = selectionEnd.value ?? { x: event.clientX, y: event.clientY }
    const box = buildSelectionBox(selectionStart.value, endPoint)
    const dragSelection = isDragging.value || box.width > CAPTURE_DRAG_THRESHOLD_PX || box.height > CAPTURE_DRAG_THRESHOLD_PX

    try {
      if (dragSelection) {
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
        overlayElement.value,
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
  }

  function handleOverlayKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault()
      cancelCaptureMode()
    }
  }

  const selectionBox = computed(() => {
    if (selectionStart.value === null || selectionEnd.value === null) {
      return null
    }
    return buildSelectionBox(selectionStart.value, selectionEnd.value)
  })

  function setOverlayElement(node: HTMLDivElement | null) {
    overlayElement.value = node
  }

  watch(isCapturing, (capturing) => {
    const body = document.body
    const bodyStyle = body.style as CSSStyleDeclaration & { webkitUserSelect?: string }

    if (capturing) {
      body.dataset.captureToolPreviousCursor = body.style.cursor
      body.dataset.captureToolPreviousUserSelect = body.style.userSelect
      body.dataset.captureToolPreviousWebkitUserSelect = bodyStyle.webkitUserSelect || ''
      body.style.cursor = 'crosshair'
      body.style.userSelect = 'none'
      bodyStyle.webkitUserSelect = 'none'
      return
    }

    body.style.cursor = body.dataset.captureToolPreviousCursor || ''
    body.style.userSelect = body.dataset.captureToolPreviousUserSelect || ''
    bodyStyle.webkitUserSelect = body.dataset.captureToolPreviousWebkitUserSelect || ''
  })

  function handleWindowKeyDown(event: KeyboardEvent) {
    const isShortcut = event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'p'

    if (isShortcut) {
      event.preventDefault()
      if (activeCapture.value) {
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

  function handleGlobalCaptureShortcut(event: KeyboardEvent) {
    const isShortcut = event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'p'
    if (!isShortcut || activeCapture.value) {
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

  onMounted(() => {
    window.addEventListener('keydown', handleGlobalCaptureShortcut)
  })

  onBeforeUnmount(() => {
    clearClickTimer()
    window.removeEventListener('keydown', handleGlobalCaptureShortcut)
    window.removeEventListener('keydown', handleWindowKeyDown)
    overlayElement.value = null

    const body = document.body
    const bodyStyle = body.style as CSSStyleDeclaration & { webkitUserSelect?: string }
    body.style.cursor = body.dataset.captureToolPreviousCursor || ''
    body.style.userSelect = body.dataset.captureToolPreviousUserSelect || ''
    bodyStyle.webkitUserSelect = body.dataset.captureToolPreviousWebkitUserSelect || ''
  })

  watch(isCapturing, (capturing) => {
    if (capturing) {
      window.addEventListener('keydown', handleWindowKeyDown)
      return
    }

    window.removeEventListener('keydown', handleWindowKeyDown)
  })

  function handleCameraSingleClick() {
    clearClickTimer()
    clickTimer.value = window.setTimeout(() => {
      beginCaptureMode()
      clickTimer.value = null
    }, CAPTURE_CLICK_DELAY_MS)
  }

  function handleCameraDoubleClick() {
    clearClickTimer()
    void captureFullPage()
  }

  return {
    isCapturing,
    selectionStart,
    selectionEnd,
    isDragging,
    statusLine,
    selectionBox,
    overlayElement,
    setOverlayElement,
    beginCaptureMode: handleCameraSingleClick,
    cancelCaptureMode,
    captureFullPage,
    handleCameraDoubleClick,
    handleOverlayMouseDown,
    handleOverlayMouseMove,
    handleOverlayMouseUp,
    handleOverlayKeyDown,
  }
}
