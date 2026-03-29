# Browser Capture To PDF Tile

This tile adds a browser-side camera tool for exporting parts of an app to PDF.

## Operator behavior
- Single click the camera button to enter capture mode.
- Press `Ctrl+Shift+P` to enter capture mode too.
- While capture mode is active, press `Ctrl+Shift+P` again to export the full page as `capture.pdf`.
- Double click the camera button to export the full page as `capture.pdf`.
- In capture mode:
  - click a visible container to export that element
  - drag to select a region and export that rectangle
  - press `Escape` to cancel

## UX details
- The helper note is intentionally small and does not appear in the PDF.
- The overlay does not dim the page, so the content looks unchanged while you select.
- The selection cursor becomes a crosshair.
- The PDF is saved as `capture.pdf` unless the host app overrides the file name.

## Provenance
- Extracted from: `/Users/slobodan/projects/Earth/AICOVENANT/frontend/src/features/captureTool`
- Captured for Active Cloner on: `2026-03-29`

## Variants
- `variants/react-vite`: ready for React apps using Vite or similar bundlers
- `variants/nuxt-vue`: translated variant for Nuxt/Vue apps

## Suggested host integration
Use this tile when an app needs:
- operator screenshots for demos or QA
- PDF exports of UI states
- lightweight region capture without backend rendering
- visual evidence capture during development or review
