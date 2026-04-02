# Translation Map: Browser Capture To PDF

This tile is maintained as one behavior with two framework variants.

## Source-of-behavior
- Canonical operator behavior comes from the extracted AICOVENANT implementation and the tile README.
- The React variant is the most direct source translation.
- The Nuxt/Vue variant must preserve behavior, shortcut semantics, and status copy.

## File mapping
- `react-vite/src/captureUtils.ts` -> `nuxt-vue/src/utils/captureUtils.ts`
- `react-vite/src/useCaptureTool.tsx` -> `nuxt-vue/src/composables/useCaptureTool.ts`
- `react-vite/src/CaptureOverlay.tsx` -> `nuxt-vue/src/components/CaptureOverlay.vue`
- `react-vite/src/CameraButton.tsx` -> `nuxt-vue/src/components/CaptureCameraButton.vue`
- `react-vite/src/captureTool.css` -> `nuxt-vue/src/styles/captureTool.css`

## Translation guardrails
- Keep keyboard shortcuts identical.
- Keep the helper HUD out of the exported PDF.
- Keep capture target selection logic semantically equivalent.
- Keep status copy human-facing and short enough for a compact top bar or helper panel.
- If one variant adds options, add them to the other variant in the same change unless the framework makes it impossible.
