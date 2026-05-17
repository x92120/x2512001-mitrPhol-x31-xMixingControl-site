/**
 * Application Configuration and Utilities
 * Refactored for Nuxt 4 & TypeScript
 */

export const appConfig = {
  // Base URL for API calls - port 8031 on the same host the browser is using
  get apiBaseUrl(): string {
    if (typeof window !== 'undefined') {
        return `${window.location.protocol}//${window.location.hostname}:8031`
    }
    return 'http://localhost:8031'
  }
}


