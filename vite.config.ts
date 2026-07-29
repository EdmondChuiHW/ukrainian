import { defineConfig } from 'vite';
import react, { reactCompilerPreset } from '@vitejs/plugin-react';
import babel from '@rolldown/plugin-babel';

const isDevelopment = process.env.NODE_ENV === 'development';

// https://vite.dev/config/
export default defineConfig({
  base: '/ukrainian/',
  plugins: [
    react(),
    babel({
      presets: [
        reactCompilerPreset({
          panicThreshold: isDevelopment ? 'all_errors' : 'none',
        }),
      ],
    }),
  ],
  server: {
    port: 5173,
    open: false,
  },
  build: {
    outDir: 'docs/',
    rollupOptions: {
      input: {
        main: 'index.html',
      },
    },
  },
});
