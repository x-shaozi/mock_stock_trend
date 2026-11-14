import { computed, ref } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'
type AppliedTheme = 'light' | 'dark'

const STORAGE_KEY = 'stock-trend-theme'
const mode = ref<ThemeMode>('system')
const systemIsDark = ref(false)
const appliedTheme = computed<AppliedTheme>(() =>
  mode.value === 'system' ? (systemIsDark.value ? 'dark' : 'light') : mode.value,
)

function applyTheme(): void {
  document.documentElement.classList.toggle('dark', appliedTheme.value === 'dark')
  document.documentElement.dataset.theme = appliedTheme.value
}

export function setThemeMode(value: ThemeMode): void {
  mode.value = value
  try {
    window.localStorage.setItem(STORAGE_KEY, value)
  } catch {
    // 禁用存储时仍可在本次浏览中切换主题。
  }
  applyTheme()
}

export function initTheme(): void {
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  systemIsDark.value = media.matches
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark' || saved === 'system') mode.value = saved
  } catch {
    // 保持默认跟随系统。
  }
  media.addEventListener('change', (event) => {
    systemIsDark.value = event.matches
    if (mode.value === 'system') applyTheme()
  })
  applyTheme()
}

export function useTheme() {
  return { themeMode: mode, appliedTheme, setThemeMode }
}
