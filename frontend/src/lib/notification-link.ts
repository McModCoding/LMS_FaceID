export function safeNotificationLink(value?: string | null): string | null {
  return value && value.startsWith('/') && !value.startsWith('//') && ![...value].some(char => char === '\\' || char.charCodeAt(0) <= 32) ? value : null
}
