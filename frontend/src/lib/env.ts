const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL

if (!configuredBaseUrl) {
  throw new Error('VITE_API_BASE_URL is required')
}

export const apiBaseUrl = configuredBaseUrl.replace(/\/$/, '')
