import { ref, computed } from 'vue'

export interface User {
    id: number
    username: string
    email: string
    full_name: string
    role: string
    department: string
    status: string
    permissions: string[]
}

// Global reactive state
const user = ref<User | null>(null)
const token = ref<string | null>(null)

/**
 * Helper: read from sessionStorage (client-side only)
 */
function loadFromSession() {
    if (import.meta.server) return            // skip during SSR
    try {
        const rawUser = sessionStorage.getItem('user')
        const rawToken = sessionStorage.getItem('token')
        if (rawUser) user.value = JSON.parse(rawUser)
        if (rawToken) token.value = rawToken
    } catch { /* ignore parse errors */ }
}

export function useAuth() {
    // Session-cookie bridge for SSR middleware (no maxAge = dies with browser)
    const cookieUser = useCookie<User | null>('user', { maxAge: undefined })
    const cookieToken = useCookie<string | null>('token', { maxAge: undefined })

    // On first call, hydrate from sessionStorage (client) or cookie (SSR)
    if (!user.value) {
        if (import.meta.client) {
            loadFromSession()
        }
        // Fallback: SSR cookie (e.g. first server render after login)
        if (!user.value && cookieUser.value) {
            user.value = cookieUser.value
        }
    }
    if (!token.value) {
        if (!token.value && cookieToken.value) {
            token.value = cookieToken.value
        }
    }

    const isAuthenticated = computed(() => !!token.value)

    /**
     * Check if user has specific permission
     */
    const hasPermission = (permission: string): boolean => {
        if (!user.value) return false
        if (user.value.role === 'Admin') return true
        return user.value.permissions?.includes(permission) || false
    }

    /**
     * Check if user has any of the provided permissions
     */
    const hasAnyPermission = (permissions: string[]): boolean => {
        if (!user.value) return false
        if (user.value.role === 'Admin') return true
        return permissions.some(p => hasPermission(p))
    }

    /**
     * Update auth state after login
     * Stores in sessionStorage (auto-cleared on browser close)
     * + session cookie for SSR bridge
     */
    const login = (userData: User, authToken: string) => {
        user.value = userData
        token.value = authToken

        // Session cookie (no maxAge = session-only, dies with browser)
        cookieUser.value = userData
        cookieToken.value = authToken

        // sessionStorage (auto-cleared when browser/tab closes)
        if (import.meta.client) {
            sessionStorage.setItem('user', JSON.stringify(userData))
            sessionStorage.setItem('token', authToken)
        }
    }

    /**
     * Clear auth state (manual logout)
     */
    const logout = () => {
        user.value = null
        token.value = null
        cookieUser.value = null
        cookieToken.value = null

        if (import.meta.client) {
            sessionStorage.removeItem('user')
            sessionStorage.removeItem('token')
        }
    }

    /**
     * Helper for fetch headers
     */
    const getAuthHeader = () => {
        return token.value ? { Authorization: `Bearer ${token.value}` } : {}
    }

    return {
        user: computed(() => user.value),
        token: computed(() => token.value),
        isAuthenticated,
        hasPermission,
        hasAnyPermission,
        login,
        logout,
        getAuthHeader,
    }
}
