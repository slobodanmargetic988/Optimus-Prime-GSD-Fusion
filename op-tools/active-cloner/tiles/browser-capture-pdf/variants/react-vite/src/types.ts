export interface CapturePoint {
  x: number
  y: number
}

export interface CaptureRect {
  x: number
  y: number
  width: number
  height: number
}

export interface CaptureToolOptions {
  fileName?: string
  captureTargetSelectors?: string[]
  onStatusChange?: (message: string) => void
}
