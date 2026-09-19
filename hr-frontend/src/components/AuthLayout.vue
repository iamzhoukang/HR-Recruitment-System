<template>
  <div
    class="flex min-h-screen flex-1 flex-col justify-center px-6 py-12 lg:px-8 bg-gradient-to-br from-green-200 to-blue-300"
  >
    <div class="sm:mx-auto sm:w-full sm:max-w-sm">
      <!-- Logo -->
      <svg
        class="mx-auto h-12 w-auto text-indigo-600"
        viewBox="0 0 24 24"
        fill="currentColor"
        aria-hidden="true"
      >
        <path
          fill-rule="evenodd"
          d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm-2.625 7.5a.75.75 0 00-1.5 0v6a.75.75 0 001.5 0v-6zm3.375 0a.75.75 0 00-1.5 0v6a.75.75 0 001.5 0v-6z"
          clip-rule="evenodd"
        />
      </svg>
      <h2 class="mt-6 text-center text-2xl font-bold leading-9 tracking-tight text-gray-900">
        {{ title }}
      </h2>
      <p v-if="subtitle" class="mt-2 text-center text-sm text-gray-500">
        {{ subtitle }}
      </p>
    </div>

    <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-sm">
      <div class="bg-white px-6 py-12 shadow sm:rounded-lg sm:px-12">
        <slot></slot>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  title: string
  subtitle?: string
}

defineProps<Props>()
</script>
