import { defineConfig } from 'vite';
import react, { reactCompilerPreset } from '@vitejs/plugin-react';
import babel from '@rolldown/plugin-babel';

const isDevelopment = process.env.NODE_ENV === 'development';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    babel({
      presets: [
        reactCompilerPreset({
          panicThreshold: isDevelopment ? 'critical_errors' : 'none',
        }),
      ],
    }),
  ],
  server: {
    port: 5173,
    open: false,
  },
  build: {
    outDir: 'dist/',
    rollupOptions: {
      input: {
        main: 'index.html',
      },
    },
  },
});
