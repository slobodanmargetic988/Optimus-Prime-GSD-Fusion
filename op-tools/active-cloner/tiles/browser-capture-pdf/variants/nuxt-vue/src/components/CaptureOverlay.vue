<script setup lang="ts">
import { ref, watch } from 'vue'

import type { CapturePoint } from '../types'

const props = withDefaults(defineProps<{
  isCapturing: boolean
  selectionStart: CapturePoint | null
  selectionEnd: CapturePoint | null
  isDragging: boolean
  statusLine: string
  helperHint?: string
  selectionBox: { left: number; top: number; width: number; height: number } | null
  overlayRef?: (node: HTMLDivElement | null) => void
}>(), {
  helperHint: 'Click a container or drag a region. The helper note will not appear in the PDF.',
})

const emit = defineEmits<{
  cancel: []
  overlayKeydown: [event: KeyboardEvent]
  overlayMousedown: [event: MouseEvent]
  overlayMousemove: [event: MouseEvent]
  overlayMouseup: [event: MouseEvent]
}>()

const overlayRoot = ref<HTMLDivElement | null>(null)

watch(
  overlayRoot,
  (node) => {
    props.overlayRef?.(node)
  },
  { immediate: true },
)
</script>

<template>
  <div
    v-if="props.isCapturing"
    ref="overlayRoot"
    class="capture-overlay"
    data-capture="camera-tool-overlay"
    tabindex="-1"
    role="presentation"
    @keydown="emit('overlayKeydown', $event)"
    @mousedown="emit('overlayMousedown', $event)"
    @mousemove="emit('overlayMousemove', $event)"
    @mouseup="emit('overlayMouseup', $event)"
  >
    <div
      class="capture-overlay__hud"
      @mousedown.stop
      @mousemove.stop
      @mouseup.stop
    >
      <p class="capture-overlay__title">{{ props.statusLine }}</p>
      <p class="capture-overlay__hint">{{ props.helperHint }}</p>
      <button
        type="button"
        class="capture-overlay__cancel"
        @mousedown.stop
        @click="emit('cancel')"
      >
        Exit capture mode
      </button>
    </div>

    <div
      v-if="props.selectionBox && props.selectionStart && props.selectionEnd"
      :class="props.isDragging ? 'capture-overlay__selection capture-overlay__selection--dragging' : 'capture-overlay__selection'"
      :style="{
        left: `${props.selectionBox.left}px`,
        top: `${props.selectionBox.top}px`,
        width: `${props.selectionBox.width}px`,
        height: `${props.selectionBox.height}px`,
      }"
    >
      <span class="capture-overlay__selection-label">
        {{ Math.round(props.selectionBox.width) }} x {{ Math.round(props.selectionBox.height) }} px
      </span>
    </div>
  </div>
</template>
