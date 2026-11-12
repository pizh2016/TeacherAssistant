<template>
  <router-view />
</template>

<script setup lang="ts">
// Teacher app root — all rendering handled by vue-router
</script>

<style>
/* Global reset */
*, *::before, *::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: #f5f7fa;
}

a {
  color: inherit;
  text-decoration: none;
}
</style>
