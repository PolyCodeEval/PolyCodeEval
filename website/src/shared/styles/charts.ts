export const chartText = {
  color: '#3f4852',
  fontFamily: 'Inter, ui-sans-serif, system-ui',
  fontSize: 11,
}
export const chartGrid = { left: 44, right: 22, top: 38, bottom: 42, containLabel: true }
export const colors = {
  blue: '#376f9e',
  orange: '#d28a3c',
  green: '#6f8e68',
  red: '#b45c57',
  purple: '#7d6fa5',
  ink: '#26333d',
  grid: '#e7ebee',
}
export const languageColors: Record<string, string> = {
  Python: '#376f9e',
  Java: '#b45c57',
  JavaScript: '#d6a238',
  Go: '#50a4ad',
  'C++': '#7d6fa5',
}
export const axis = {
  axisLabel: chartText,
  axisLine: { lineStyle: { color: '#9aa5ad' } },
  splitLine: { lineStyle: { color: colors.grid } },
}
