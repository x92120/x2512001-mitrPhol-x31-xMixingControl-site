import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

const dirname =
  typeof __dirname !== 'undefined' ? __dirname : path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  test: {
    projects: [
      // ── Unit / composable tests (Node, no browser) ──
      {
        test: {
          name: 'unit',
          include: ['app/**/*.{test,spec}.{ts,js}', 'tests/**/*.{test,spec}.{ts,js}'],
          environment: 'node',
          globals: true,
          alias: {
            '~': path.join(dirname, 'app'),
            '~/': path.join(dirname, 'app/'),
          },
        },
      },
    ],
  },
});

