import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'

import type { CaptureRect } from '../types'

const DEFAULT_FILE_NAME = 'capture.pdf'
const DEFAULT_CAPTURE_SCALE = 2
const DEFAULT_CAPTURE_TARGET_SELECTORS = [
  '[data-capture]',
  '.panel',
  '.topbar',
  '.sidebar',
  '.content-stage',
  '.page-header',
  '.shell-page',
  'section',
  'article',
  'main',
  'aside',
  'header',
  'nav',
]

type Html2CanvasOptions = Parameters<typeof html2canvas>[1]

function normalizeRect(rect: CaptureRect): CaptureRect {
  const x = Number.isFinite(rect.x) ? rect.x : 0
  const y = Number.isFinite(rect.y) ? rect.y : 0
  const width = Math.max(1, Number.isFinite(rect.width) ? rect.width : 1)
  const height = Math.max(1, Number.isFinite(rect.height) ? rect.height : 1)

  return { x, y, width, height }
}

function createCanvasForTarget(element: HTMLElement, options?: Html2CanvasOptions) {
  return html2canvas(element, {
    backgroundColor: '#ffffff',
    scale: DEFAULT_CAPTURE_SCALE,
    useCORS: true,
    ...options,
  })
}

function addCanvasToPdf(canvas: HTMLCanvasElement, fileName: string) {
  const pdf = new jsPDF('p', 'mm', 'a4')
  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = pdf.internal.pageSize.getHeight()
  const imageWidth = pageWidth
  const imageHeight = (canvas.height * imageWidth) / canvas.width
  const imageData = canvas.toDataURL('image/png')

  let remainingHeight = imageHeight
  let position = 0

  pdf.addImage(imageData, 'PNG', 0, position, imageWidth, imageHeight)
  remainingHeight -= pageHeight

  while (remainingHeight > 0) {
    position = remainingHeight - imageHeight
    pdf.addPage()
    pdf.addImage(imageData, 'PNG', 0, position, imageWidth, imageHeight)
    remainingHeight -= pageHeight
  }

  pdf.save(fileName || DEFAULT_FILE_NAME)
}

function resolveTargetSelectors(selectors?: string[]) {
  return (selectors && selectors.length > 0 ? selectors : DEFAULT_CAPTURE_TARGET_SELECTORS).join(',')
}

function getCaptureTargetFromPoint(
  clientX: number,
  clientY: number,
  overlayElement?: HTMLElement | null,
  captureTargetSelectors?: string[],
) {
  const overlay = overlayElement ?? null

  if (overlay) {
    overlay.style.pointerEvents = 'none'
  }

  try {
    const rawTarget = document.elementFromPoint(clientX, clientY)
    if (!(rawTarget instanceof Element)) {
      return null
    }

    const semanticTarget = rawTarget.closest(resolveTargetSelectors(captureTargetSelectors))
    if (semanticTarget instanceof HTMLElement) {
      return semanticTarget
    }

    if (rawTarget instanceof HTMLElement) {
      return rawTarget
    }

    return null
  } finally {
    if (overlay) {
      overlay.style.pointerEvents = 'auto'
    }
  }
}

export async function captureElement(element: HTMLElement, fileName: string = DEFAULT_FILE_NAME): Promise<void> {
  const canvas = await createCanvasForTarget(element)
  addCanvasToPdf(canvas, fileName)
}

export async function captureArea(rect: CaptureRect, fileName: string = DEFAULT_FILE_NAME): Promise<void> {
  const normalizedRect = normalizeRect(rect)
  const canvas = await createCanvasForTarget(document.body, {
    x: normalizedRect.x,
    y: normalizedRect.y,
    width: normalizedRect.width,
    height: normalizedRect.height,
    scrollX: 0,
    scrollY: 0,
  })

  addCanvasToPdf(canvas, fileName)
}

export function resolveCaptureTargetFromPoint(
  clientX: number,
  clientY: number,
  overlayElement?: HTMLElement | null,
  captureTargetSelectors?: string[],
): HTMLElement | null {
  return getCaptureTargetFromPoint(clientX, clientY, overlayElement, captureTargetSelectors)
}
