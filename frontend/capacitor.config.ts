import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.omedia.app',
  appName: 'OMedia',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
    // For development, uncomment to use live reload
    // url: 'http://YOUR_IP:3000',
    // cleartext: true
  },
  plugins: {
    App: {
      // Enable app state change detection for clipboard
    },
    Clipboard: {
      // Clipboard plugin configuration
    },
    StatusBar: {
      style: 'dark',
    },
  },
};

export default config;

