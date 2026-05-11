<template>
  <div class="app">
    <header class="header">
      <h1 class="header-title">U-Word 投稿管理</h1>
    </header>
    <main class="main">
      <Poster />
    </main>
  </div>
</template>

<script setup lang="ts">
import Poster from './views/Poster.vue'
</script>

<style>
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body, html, #app {
  background: linear-gradient(135deg, #ffe8f0 0%, #f5e8ff 50%, #e8f0ff 100%);
  margin: 0;
  padding: 0;
  min-height: 100vh;
}

body {
  background: linear-gradient(135deg, #ffe8f0 0%, #f5e8ff 50%, #e8f0ff 100%);
  color: #3d1a4a;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Hiragino Sans', 'Noto Sans JP', Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  min-height: 100vh;
}

#app {
  background: linear-gradient(135deg, #ffe8f0 0%, #f5e8ff 50%, #e8f0ff 100%);
  background-attachment: fixed;
}

.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(231, 84, 128, 0.15);
  padding: 14px 24px;
  box-shadow: 0 2px 20px rgba(231, 84, 128, 0.08);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-title {
  font-size: 18px;
  font-weight: 700;
  background: linear-gradient(135deg, #e75480, #9b59b6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: 0.5px;
}

.main {
  flex: 1;
  padding: 24px;
}
</style>
