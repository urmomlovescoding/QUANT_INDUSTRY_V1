/**
 * QUANT INDUSTRY Desktop - Preload Script
 * Secure bridge between renderer and main process
 *
 * This script runs in the renderer process before web content loads,
 * providing secure access to Node.js APIs through contextBridge.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose secure APIs to renderer
contextBridge.exposeInMainWorld('electronAPI', {
  // ============================================
  // System Resources
  // ============================================
  getSystemResources: () => ipcRenderer.invoke('get-system-resources'),
  onSystemResources: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('system-resources', handler);
    return () => ipcRenderer.removeListener('system-resources', handler);
  },

  // ============================================
  // Configuration
  // ============================================
  getConfig: (key) => ipcRenderer.invoke('get-config', key),
  setConfig: (key, value) => ipcRenderer.invoke('set-config', key, value),
  getAllConfig: () => ipcRenderer.invoke('get-all-config'),

  // ============================================
  // Backend Control
  // ============================================
  startBackend: () => ipcRenderer.invoke('start-backend'),
  stopBackend: () => ipcRenderer.invoke('stop-backend'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),

  onBackendLog: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('backend-log', handler);
    return () => ipcRenderer.removeListener('backend-log', handler);
  },

  onBackendError: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('backend-error', handler);
    return () => ipcRenderer.removeListener('backend-error', handler);
  },

  onBackendStatus: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('backend-status', handler);
    return () => ipcRenderer.removeListener('backend-status', handler);
  },

  // ============================================
  // Python Script Execution
  // ============================================
  runPythonScript: (scriptName, args) => ipcRenderer.invoke('run-python-script', scriptName, args),

  // ============================================
  // GPU Detection
  // ============================================
  detectGPU: () => ipcRenderer.invoke('detect-gpu'),

  // ============================================
  // Navigation (from menu)
  // ============================================
  onNavigate: (callback) => {
    const handler = (event, path) => callback(path);
    ipcRenderer.on('navigate', handler);
    return () => ipcRenderer.removeListener('navigate', handler);
  },

  // ============================================
  // Bot Control (from menu/tray)
  // ============================================
  onBotControl: (callback) => {
    const handler = (event, action) => callback(action);
    ipcRenderer.on('bot-control', handler);
    return () => ipcRenderer.removeListener('bot-control', handler);
  },

  // ============================================
  // External Links
  // ============================================
  openExternal: (url) => ipcRenderer.invoke('open-external', url),

  // ============================================
  // Notifications
  // ============================================
  showNotification: (title, body) => ipcRenderer.invoke('show-notification', title, body),

  // ============================================
  // Platform Info
  // ============================================
  platform: process.platform,
  arch: process.arch,
  electronVersion: process.versions.electron,
  nodeVersion: process.versions.node,
  chromeVersion: process.versions.chrome,

  // ============================================
  // Desktop Detection
  // ============================================
  isElectron: true
});

// Log that preload script is loaded
console.log('%c QUANT INDUSTRY Desktop ', 'background: #00d4aa; color: #0a0a12; font-weight: bold; padding: 4px 8px; border-radius: 4px;', 'Preload script loaded');
console.log('Platform:', process.platform);
console.log('Electron:', process.versions.electron);
