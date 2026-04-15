export default defineNuxtRouteMiddleware((to, from) => {
    const { user, hasPermission } = useAuth()

    // Public pages (exact matches or starts with)
    const publicPages = ['/x80-UserLogin', '/x81-UserRegister', '/', '/x99-About']

    if (publicPages.includes(to.path)) {
        return
    }

    // Check if user is logged in
    if (!user.value) {
        return navigateTo({
            path: '/x80-UserLogin',
            query: { redirect: to.fullPath }
        })
    }

    // Check for specific permissions based on the path
    const permissionMap: Record<string, string> = {
        '/x89-UserConfig': 'admin',

        '/x11-IngredientConfig': 'ingredient_receipt',
        '/x12-WarehouseConfig': 'ingredient_receipt',





        '/x60-BatchRecheck': 'production_list',
        '/x90-systemDashboard': 'admin',
    }

    const requiredPermission = permissionMap[to.path]
    if (requiredPermission && !hasPermission(requiredPermission)) {
        return navigateTo({
            path: '/',
            query: { error: 'no-permission' }
        })
    }
})
