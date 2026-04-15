/**
 * Application Configuration and Utilities
 * Refactored for Nuxt 4 & TypeScript
 */

export const appConfig = {
  // Base URL for API calls - always port 8001 on the same host the browser is using
  get apiBaseUrl(): string {
    // Toplogy deployment target: x11 API server
    if (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
        return `http://${window.location.hostname}:8001`
    }
    return 'http://192.168.121.11:8001'
  }
}


