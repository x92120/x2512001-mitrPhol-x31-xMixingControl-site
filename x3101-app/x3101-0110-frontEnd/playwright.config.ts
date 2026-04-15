import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
    testDir: '.',
    testMatch: 'screenshot-capture.spec.ts',
    fullyParallel: false,
    forbidOnly: !!process.env.CI,
    retries: 0,
    workers: 1,
    reporter: 'list',
    timeout: 60000,

    use: {
        baseURL: 'http://localhost:3000',
        trace: 'off',
        screenshot: 'off',
        video: 'off',
        viewport: { width: 1920, height: 1080 },
    },

    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],

    // Don't start server - assume it's already running
    webServer: undefined,
});
