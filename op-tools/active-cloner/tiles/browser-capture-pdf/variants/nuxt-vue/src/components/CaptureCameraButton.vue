<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

const props = defineProps<{
  isActive: boolean
  statusLine: string
}>()

const emit = defineEmits<{
  singleClick: []
  doubleClick: []
}>()

const clickTimer = ref<number | null>(null)

function clearClickTimer() {
  if (clickTimer.value !== null) {
    window.clearTimeout(clickTimer.value)
    clickTimer.value = null
  }
}

function handleClick() {
  clearClickTimer()
  clickTimer.value = window.setTimeout(() => {
    emit('singleClick')
    clickTimer.value = null
  }, 220)
}

function handleDoubleClick() {
  clearClickTimer()
  emit('doubleClick')
}

onBeforeUnmount(() => {
  clearClickTimer()
})
</script>

<template>
  <button
    type="button"
    :class="props.isActive ? 'camera-button camera-button--active' : 'camera-button'"
    :aria-pressed="props.isActive"
    title="Single click or Ctrl+Shift+P to enter capture mode. Double click to export the full page."
    @click="handleClick"
    @dblclick="handleDoubleClick"
  >
    <svg class="camera-button__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M7.5 6.5h2.25l1.1-1.75h2.8l1.1 1.75H17a2.5 2.5 0 0 1 2.5 2.5v6.5A2.5 2.5 0 0 1 17 18H7a2.5 2.5 0 0 1-2.5-2.5V9A2.5 2.5 0 0 1 7 6.5Z" />
      <circle cx="12" cy="12" r="3.5" />
    </svg>
    <span class="camera-button__copy">
      <strong>Camera tool</strong>
      <span>{{ props.statusLine }}</span>
    </span>
  </button>
</template>
