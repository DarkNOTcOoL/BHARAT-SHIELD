import {defineConfig} from 'vitest/config';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],define:{'import.meta.env.TEST':'true'},test:{environment:'jsdom',include:['src/**/*.test.jsx','src/**/*.test.js'],pool:'threads',poolOptions:{threads:{singleThread:true}}}});
