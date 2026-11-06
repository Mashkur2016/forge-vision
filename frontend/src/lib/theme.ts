export type Theme = 'light' | 'dark'

export function getStoredTheme(): Theme {
  return (localStorage.getItem('forge-theme') as Theme) ?? 'light'
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  localStorage.setItem('forge-theme', theme)
}
