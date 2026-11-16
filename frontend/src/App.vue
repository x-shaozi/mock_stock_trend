<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useTheme, type ThemeMode } from './composables/useTheme'

const { themeMode, setThemeMode } = useTheme()
const selectedTheme = computed<ThemeMode>({
  get: () => themeMode.value,
  set: (value) => setThemeMode(value),
})
</script>

<template>
  <el-container class="app-shell">
    <el-aside
      class="sidebar"
      width="228px"
    >
      <div class="brand">
        <span class="brand-mark">↗</span>
        <div><strong>Stock Trend Lab</strong><small>股票趋势分析平台</small></div>
      </div>
      <nav
        class="main-nav"
        aria-label="主导航"
      >
        <RouterLink
          to="/stocks"
          class="nav-item"
          >我的股票</RouterLink
        >
        <RouterLink
          to="/stocks/add"
          class="nav-item"
          >添加股票</RouterLink
        >
        <RouterLink
          to="/stocks/archived"
          class="nav-item"
          >已归档股票</RouterLink
        >
      </nav>
      <div class="sidebar-foot">S3 · 趋势分析</div>
    </el-aside>
    <el-container class="main-layout">
      <el-header class="topbar">
        <div class="topbar-name">股票趋势分析工作台</div>
        <label class="theme-selector">
          <span>外观</span>
          <el-select
            v-model="selectedTheme"
            aria-label="外观主题"
            style="width: 130px"
          >
            <el-option
              label="跟随系统"
              value="system"
            />
            <el-option
              label="浅色模式"
              value="light"
            />
            <el-option
              label="深色模式"
              value="dark"
            />
          </el-select>
        </label>
      </el-header>
      <el-main><RouterView /></el-main>
    </el-container>
  </el-container>
</template>
