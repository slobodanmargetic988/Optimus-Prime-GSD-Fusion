# Nuxt/Vue Variant: Browser Capture To PDF

## Dependencies
- `html2canvas`
- `jspdf`

## Exported modules
- `CaptureCameraButton.vue`
- `CaptureOverlay.vue`
- `useCaptureTool`
- `captureElement`
- `captureArea`
- `resolveCaptureTargetFromPoint`

## Typical integration
1. Import `src/styles/captureTool.css` into your Nuxt app or layout.
2. Call `useCaptureTool()` from the host component.
3. Render `CaptureCameraButton` in the shell.
4. Render `CaptureOverlay` while capture mode is active.
5. Pass `setOverlayElement` into `CaptureOverlay` as `:overlay-ref="setOverlayElement"` so click-to-capture can resolve the underlying target.
6. Pass hook state and actions into both components.

## Nuxt note
This variant assumes client-only execution for capture actions because `html2canvas` and `document` access are browser-only.
