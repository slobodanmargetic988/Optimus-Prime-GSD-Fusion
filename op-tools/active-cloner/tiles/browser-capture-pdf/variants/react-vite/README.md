# React Variant: Browser Capture To PDF

## Dependencies
- `html2canvas`
- `jspdf`

## Exported modules
- `CaptureCameraButton`
- `CaptureOverlay`
- `useCaptureTool`
- `captureElement`
- `captureArea`
- `resolveCaptureTargetFromPoint`

## Typical integration
1. Import `captureTool.css`.
2. Mount `CaptureCameraButton` in your shell or top bar.
3. Call `useCaptureTool()` in the host component.
4. Render `CaptureOverlay` whenever `isCapturing` is true.
5. Feed the hook's handlers and status line into the button and overlay.

## Host note
Pass `onStatusChange` if the host wants to mirror status updates into a terminal-like panel or app event log.
