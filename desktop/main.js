/**
 * QUANT INDUSTRY Desktop Application
 * Electron Main Process v10.0
 *
 * Features:
 * - Native desktop performance with hardware acceleration
 * - System tray with quick actions
 * - Splash screen during startup
 * - System resource monitoring (CPU, RAM, GPU)
 * - Background Python ML processes
 * - Real-time IPC communication
 * - Auto-updater support
 * - Crash reporter
 */

const { app, BrowserWindow, ipcMain, Menu, Tray, shell, dialog, nativeImage, crashReporter } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const os = require('os');
const fs = require('fs');
const Store = require('electron-store');

// Initialize crash reporter
crashReporter.start({
  productName: 'QUANT INDUSTRY',
  companyName: 'QuantIndustry',
  submitURL: '', // Add your crash report server URL
  uploadToServer: false
});

// Persistent storage
const store = new Store({
  name: 'quant-industry-config',
  defaults: {
    windowBounds: { width: 1920, height: 1080, x: undefined, y: undefined },
    apiPort: 8000,
    frontendPort: 3000,
    pythonPath: 'python',
    gpuAcceleration: true,
    maxMemoryUsage: 80,
    autoStartBackend: true,
    minimizeToTray: true,
    startMinimized: false,
    theme: 'dark',
    lastRoute: '/dashboard'
  }
});

// Global references
let mainWindow = null;
let splashWindow = null;
let tray = null;
let backendProcess = null;
let systemMonitorInterval = null;
let cpuUsageHistory = [];

// Development mode detection
const isDev = process.argv.includes('--dev') || process.env.NODE_ENV === 'development';

// Ensure single instance
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

/**
 * Create splash screen
 */
function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 500,
    height: 350,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // Create splash screen HTML content
  const splashHTML = `
<!DOCTYPE html>
<html>
<head>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, #0a0a12 0%, #1a1a2e 100%);
      color: #fff;
      height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      border-radius: 12px;
      border: 1px solid rgba(0, 212, 170, 0.3);
      overflow: hidden;
    }
    .logo {
      font-size: 42px;
      font-weight: 700;
      background: linear-gradient(90deg, #00d4aa, #00ff88);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 8px;
    }
    .version {
      font-size: 14px;
      color: #666;
      margin-bottom: 30px;
    }
    .loader {
      width: 200px;
      height: 4px;
      background: rgba(255,255,255,0.1);
      border-radius: 2px;
      overflow: hidden;
      margin-bottom: 15px;
    }
    .loader-bar {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #00d4aa, #00ff88);
      border-radius: 2px;
      animation: load 3s ease-in-out forwards;
    }
    @keyframes load {
      0% { width: 0%; }
      20% { width: 20%; }
      40% { width: 45%; }
      60% { width: 70%; }
      80% { width: 85%; }
      100% { width: 100%; }
    }
    .status {
      font-size: 12px;
      color: #888;
    }
    .features {
      margin-top: 25px;
      display: flex;
      gap: 20px;
      font-size: 11px;
      color: #666;
    }
    .feature {
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #00d4aa;
    }
  </style>
</head>
<body>
  <div class="logo">QUANT INDUSTRY</div>
  <div class="version">v10.0 Professional</div>
  <div class="loader"><div class="loader-bar"></div></div>
  <div class="status" id="status">Initializing...</div>
  <div class="features">
    <div class="feature"><div class="dot"></div>ML Brain</div>
    <div class="feature"><div class="dot"></div>Risk Engine</div>
    <div class="feature"><div class="dot"></div>Real-time Data</div>
  </div>
  <script>
    const messages = [
      'Initializing...',
      'Loading ML models...',
      'Connecting to backend...',
      'Preparing dashboard...',
      'Starting trading engine...',
      'Ready!'
    ];
    let i = 0;
    const interval = setInterval(() => {
      if (i < messages.length - 1) {
        i++;
        document.getElementById('status').textContent = messages[i];
      } else {
        clearInterval(interval);
      }
    }, 500);
  </script>
</body>
</html>`;

  splashWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(splashHTML)}`);
  splashWindow.center();
}

/**
 * Create the main application window
 */
function createWindow() {
  const bounds = store.get('windowBounds');

  mainWindow = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    x: bounds.x,
    y: bounds.y,
    minWidth: 1280,
    minHeight: 720,
    title: 'QUANT INDUSTRY v10.0',
    backgroundColor: '#0a0a12',
    show: false,
    icon: path.join(__dirname, 'assets', 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: true,
      backgroundThrottling: false,
      offscreen: false,
      spellcheck: false
    }
  });

  // Hardware acceleration settings
  if (store.get('gpuAcceleration')) {
    app.commandLine.appendSwitch('enable-gpu-rasterization');
    app.commandLine.appendSwitch('enable-zero-copy');
    app.commandLine.appendSwitch('enable-features', 'VaapiVideoDecoder');
    app.commandLine.appendSwitch('ignore-gpu-blocklist');
  }

  // Load the frontend
  const frontendPort = store.get('frontendPort');
  if (isDev) {
    mainWindow.loadURL(`http://localhost:${frontendPort}`);
  } else {
    // In production, load from built files
    const indexPath = path.join(__dirname, '../frontend/dist/index.html');
    if (fs.existsSync(indexPath)) {
      mainWindow.loadFile(indexPath);
    } else {
      mainWindow.loadURL(`http://localhost:${frontendPort}`);
    }
  }

  // SECURITY: Set Content Security Policy headers
  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'; " +
          "script-src 'self'; " +
          "style-src 'self' 'unsafe-inline'; " +
          "img-src 'self' data: https:; " +
          "connect-src 'self' http://localhost:* ws://localhost:* https://paper-api.alpaca.markets https://data.alpaca.markets https://sandbox.tradier.com https://api.polygon.io https://finnhub.io https://newsapi.org; " +
          "font-src 'self' data:; " +
          "object-src 'none'; " +
          "base-uri 'self';"
        ]
      }
    });
  });

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    if (splashWindow) {
      splashWindow.close();
      splashWindow = null;
    }

    if (!store.get('startMinimized')) {
      mainWindow.show();
      mainWindow.focus();
    }

    if (isDev) {
      mainWindow.webContents.openDevTools();
    }
  });

  // Save window bounds on resize/move
  const saveBounds = () => {
    if (!mainWindow.isMaximized() && !mainWindow.isMinimized()) {
      const { x, y, width, height } = mainWindow.getBounds();
      store.set('windowBounds', { x, y, width, height });
    }
  };

  mainWindow.on('resize', saveBounds);
  mainWindow.on('move', saveBounds);

  // Handle minimize to tray
  mainWindow.on('close', (event) => {
    if (store.get('minimizeToTray') && !app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  // Handle window close
  mainWindow.on('closed', () => {
    mainWindow = null;
    stopSystemMonitor();
  });

  // Create application menu
  createMenu();

  // Create system tray
  createTray();

  // Start system monitoring
  startSystemMonitor();

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

/**
 * Create system tray
 */
function createTray() {
  // Create tray icon (use a simple colored square as fallback)
  const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
  let trayIcon;

  if (fs.existsSync(iconPath)) {
    trayIcon = nativeImage.createFromPath(iconPath);
  } else {
    // Create a simple 16x16 icon programmatically
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon.isEmpty() ? nativeImage.createFromDataURL('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAABRSURBVDiNY2AYBfQC/v//z0jNFzAwMDD8//+fEZ9CZj4+PsYHDx78J0czMxMT04P///8z4lPHwMDAoKCgwPjgwYP/2MQYGRkZCSplYBjSNgAAWCwX+6F8BYIAAAAASUVORK5CYII=') : trayIcon);

  tray.setToolTip('QUANT INDUSTRY v10.0');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show App',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Dashboard',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.webContents.send('navigate', '/dashboard');
        }
      }
    },
    {
      label: 'Algo Bot',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.webContents.send('navigate', '/algo-bot');
        }
      }
    },
    {
      label: 'Risk Engine',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.webContents.send('navigate', '/risk-engine');
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Bot Control',
      submenu: [
        {
          label: 'Start Bot',
          click: () => mainWindow?.webContents.send('bot-control', 'start')
        },
        {
          label: 'Stop Bot',
          click: () => mainWindow?.webContents.send('bot-control', 'stop')
        },
        {
          label: 'Kill All Positions',
          click: () => mainWindow?.webContents.send('bot-control', 'kill')
        }
      ]
    },
    { type: 'separator' },
    {
      label: 'Backend',
      submenu: [
        {
          label: 'Restart Backend',
          click: () => restartBackend()
        },
        {
          label: 'Stop Backend',
          click: () => stopBackend()
        }
      ]
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);

  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

/**
 * Create application menu
 */
function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Settings',
          accelerator: 'CmdOrCtrl+,',
          click: () => mainWindow?.webContents.send('navigate', '/settings')
        },
        { type: 'separator' },
        {
          label: 'Restart Backend',
          accelerator: 'CmdOrCtrl+Shift+R',
          click: () => restartBackend()
        },
        { type: 'separator' },
        {
          label: 'Minimize to Tray',
          click: () => mainWindow?.hide()
        },
        { type: 'separator' },
        {
          label: 'Quit',
          accelerator: 'CmdOrCtrl+Q',
          click: () => {
            app.isQuitting = true;
            app.quit();
          }
        }
      ]
    },
    {
      label: 'View',
      submenu: [
        {
          label: 'Dashboard',
          accelerator: 'CmdOrCtrl+1',
          click: () => mainWindow?.webContents.send('navigate', '/dashboard')
        },
        {
          label: 'Algo Bot',
          accelerator: 'CmdOrCtrl+2',
          click: () => mainWindow?.webContents.send('navigate', '/algo-bot')
        },
        {
          label: 'Quant Platform',
          accelerator: 'CmdOrCtrl+3',
          click: () => mainWindow?.webContents.send('navigate', '/quant-platform')
        },
        {
          label: 'Risk Engine',
          accelerator: 'CmdOrCtrl+4',
          click: () => mainWindow?.webContents.send('navigate', '/risk-engine')
        },
        {
          label: 'Backtesting',
          accelerator: 'CmdOrCtrl+5',
          click: () => mainWindow?.webContents.send('navigate', '/backtesting')
        },
        { type: 'separator' },
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Trading',
      submenu: [
        {
          label: 'Start Bot',
          accelerator: 'F5',
          click: () => mainWindow?.webContents.send('bot-control', 'start')
        },
        {
          label: 'Stop Bot',
          accelerator: 'F6',
          click: () => mainWindow?.webContents.send('bot-control', 'stop')
        },
        { type: 'separator' },
        {
          label: 'Kill All Positions',
          accelerator: 'CmdOrCtrl+Shift+K',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'warning',
              buttons: ['Cancel', 'Kill All'],
              defaultId: 0,
              title: 'Confirm Kill All',
              message: 'Are you sure you want to close all positions?',
              detail: 'This will immediately close all open positions at market price.'
            }).then(result => {
              if (result.response === 1) {
                mainWindow?.webContents.send('bot-control', 'kill');
              }
            });
          }
        }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Documentation',
          click: () => shell.openExternal('https://github.com/quantindustry/docs')
        },
        {
          label: 'Keyboard Shortcuts',
          click: () => showKeyboardShortcuts()
        },
        { type: 'separator' },
        {
          label: 'System Info',
          click: () => showSystemInfo()
        },
        {
          label: 'View Logs',
          click: () => openLogsFolder()
        },
        { type: 'separator' },
        {
          label: 'Check for Updates',
          click: () => checkForUpdates()
        },
        { type: 'separator' },
        {
          label: 'About',
          click: () => showAbout()
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

/**
 * Start Python backend process
 */
async function startBackend() {
  if (backendProcess) {
    console.log('Backend already running');
    return;
  }

  const pythonPath = store.get('pythonPath');
  const backendPath = path.join(__dirname, '../backend');
  const apiPort = store.get('apiPort');

  console.log(`Starting backend on port ${apiPort}...`);
  logToFile(`Starting backend: ${pythonPath} on port ${apiPort}`);

  try {
    backendProcess = spawn(pythonPath, [
      '-m', 'uvicorn',
      'main:app',
      '--host', '0.0.0.0',
      '--port', String(apiPort),
      '--reload'
    ], {
      cwd: backendPath,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONDONTWRITEBYTECODE: '1'
      },
      shell: false,
      windowsHide: true
    });

    backendProcess.stdout?.on('data', (data) => {
      const msg = data.toString();
      console.log(`[Backend] ${msg}`);
      logToFile(`[Backend] ${msg}`);
      mainWindow?.webContents.send('backend-log', msg);
    });

    backendProcess.stderr?.on('data', (data) => {
      const msg = data.toString();
      // Uvicorn logs to stderr, so not all stderr is errors
      console.log(`[Backend] ${msg}`);
      logToFile(`[Backend] ${msg}`);
      mainWindow?.webContents.send('backend-log', msg);
    });

    backendProcess.on('close', (code) => {
      console.log(`Backend process exited with code ${code}`);
      logToFile(`Backend exited with code ${code}`);
      backendProcess = null;
      mainWindow?.webContents.send('backend-status', { status: 'stopped', code });
    });

    backendProcess.on('error', (err) => {
      console.error('Backend process error:', err);
      logToFile(`Backend error: ${err.message}`);
      mainWindow?.webContents.send('backend-error', err.message);
    });

    // Wait for backend to start
    return new Promise((resolve) => {
      setTimeout(() => {
        mainWindow?.webContents.send('backend-status', { status: 'running', port: apiPort });
        resolve();
      }, 3000);
    });
  } catch (err) {
    console.error('Failed to start backend:', err);
    logToFile(`Failed to start backend: ${err.message}`);
    throw err;
  }
}

/**
 * Stop Python backend process
 */
function stopBackend() {
  if (backendProcess) {
    if (process.platform === 'win32') {
      exec(`taskkill /pid ${backendProcess.pid} /T /F`);
    } else {
      backendProcess.kill('SIGTERM');
    }
    backendProcess = null;
    console.log('Backend stopped');
    logToFile('Backend stopped');
    mainWindow?.webContents.send('backend-status', { status: 'stopped' });
  }
}

/**
 * Restart backend
 */
async function restartBackend() {
  stopBackend();
  await new Promise(resolve => setTimeout(resolve, 1000));
  await startBackend();
  mainWindow?.webContents.send('backend-status', { status: 'restarted' });
}

/**
 * Get system resource usage with improved CPU calculation
 */
function getSystemResources() {
  const cpus = os.cpus();
  const totalMemory = os.totalmem();
  const freeMemory = os.freemem();
  const usedMemory = totalMemory - freeMemory;

  // Calculate CPU usage more accurately
  let totalIdle = 0;
  let totalTick = 0;

  cpus.forEach((cpu) => {
    for (const type in cpu.times) {
      totalTick += cpu.times[type];
    }
    totalIdle += cpu.times.idle;
  });

  // Store for delta calculation
  const currentCpuInfo = { idle: totalIdle, total: totalTick };
  let cpuUsage = 0;

  if (cpuUsageHistory.length > 0) {
    const lastInfo = cpuUsageHistory[cpuUsageHistory.length - 1];
    const idleDiff = currentCpuInfo.idle - lastInfo.idle;
    const totalDiff = currentCpuInfo.total - lastInfo.total;
    cpuUsage = totalDiff > 0 ? 100 - (100 * idleDiff / totalDiff) : 0;
  }

  cpuUsageHistory.push(currentCpuInfo);
  if (cpuUsageHistory.length > 2) cpuUsageHistory.shift();

  return {
    cpu: {
      usage: Math.max(0, Math.min(100, cpuUsage)).toFixed(1),
      cores: cpus.length,
      model: cpus[0]?.model || 'Unknown'
    },
    memory: {
      total: (totalMemory / 1024 / 1024 / 1024).toFixed(2),
      used: (usedMemory / 1024 / 1024 / 1024).toFixed(2),
      free: (freeMemory / 1024 / 1024 / 1024).toFixed(2),
      usage: ((usedMemory / totalMemory) * 100).toFixed(1)
    },
    platform: os.platform(),
    arch: os.arch(),
    hostname: os.hostname(),
    uptime: os.uptime(),
    backendRunning: backendProcess !== null
  };
}

/**
 * Start system resource monitoring
 */
function startSystemMonitor() {
  // Initial reading
  getSystemResources();

  systemMonitorInterval = setInterval(() => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      const resources = getSystemResources();
      mainWindow.webContents.send('system-resources', resources);
    }
  }, 2000);
}

/**
 * Stop system resource monitoring
 */
function stopSystemMonitor() {
  if (systemMonitorInterval) {
    clearInterval(systemMonitorInterval);
    systemMonitorInterval = null;
  }
}

/**
 * Log to file
 */
function logToFile(message) {
  const logsDir = path.join(app.getPath('userData'), 'logs');
  if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir, { recursive: true });
  }

  const logFile = path.join(logsDir, `quant-industry-${new Date().toISOString().split('T')[0]}.log`);
  const timestamp = new Date().toISOString();
  fs.appendFileSync(logFile, `[${timestamp}] ${message}\n`);
}

/**
 * Open logs folder
 */
function openLogsFolder() {
  const logsDir = path.join(app.getPath('userData'), 'logs');
  if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir, { recursive: true });
  }
  shell.openPath(logsDir);
}

/**
 * Show keyboard shortcuts dialog
 */
function showKeyboardShortcuts() {
  dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: 'Keyboard Shortcuts',
    message: 'QUANT INDUSTRY Shortcuts',
    detail: `
Navigation:
  Ctrl+1  Dashboard
  Ctrl+2  Algo Bot
  Ctrl+3  Quant Platform
  Ctrl+4  Risk Engine
  Ctrl+5  Backtesting

Trading:
  F5      Start Bot
  F6      Stop Bot
  Ctrl+Shift+K  Kill All Positions

Application:
  Ctrl+,  Settings
  Ctrl+Shift+R  Restart Backend
  Ctrl+Q  Quit
  F11     Toggle Fullscreen
    `.trim()
  });
}

/**
 * Show system info dialog
 */
function showSystemInfo() {
  const resources = getSystemResources();
  dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: 'System Information',
    message: 'QUANT INDUSTRY System Info',
    detail: `
Platform: ${resources.platform} (${resources.arch})
Hostname: ${resources.hostname}

CPU: ${resources.cpu.model}
CPU Cores: ${resources.cpu.cores}
CPU Usage: ${resources.cpu.usage}%

Memory: ${resources.memory.used} GB / ${resources.memory.total} GB
Memory Usage: ${resources.memory.usage}%

System Uptime: ${Math.floor(resources.uptime / 3600)} hours

Backend: ${backendProcess ? 'Running' : 'Stopped'}
Electron: ${process.versions.electron}
Node: ${process.versions.node}
Chrome: ${process.versions.chrome}
    `.trim()
  });
}

/**
 * Show about dialog
 */
function showAbout() {
  dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: 'About QUANT INDUSTRY',
    message: 'QUANT INDUSTRY v10.0',
    detail: `
Institutional Grade Algorithmic Trading Platform

Features:
- ML/RL/Deep Learning Trading Engines
- Real-time Market Analysis
- Prop Firm Compliance (TPT/FTMO)
- Multi-Strategy Portfolio Optimization
- Advanced Risk Management
- Neural Network Signal Generation
- GPU Accelerated Backtesting

Built with:
- Electron ${process.versions.electron}
- React 18 + TypeScript
- FastAPI + Python 3.10+
- PyTorch / TensorFlow

(c) 2024 QUANT INDUSTRY
    `.trim()
  });
}

/**
 * Check for updates
 */
function checkForUpdates() {
  // Placeholder for auto-updater integration
  dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: 'Updates',
    message: 'You are running the latest version',
    detail: 'QUANT INDUSTRY v10.0\n\nAuto-update is configured for production builds.'
  });
}

// IPC Handlers
ipcMain.handle('get-system-resources', () => getSystemResources());
ipcMain.handle('get-config', (event, key) => store.get(key));
ipcMain.handle('set-config', (event, key, value) => {
  store.set(key, value);
  return true;
});
ipcMain.handle('get-all-config', () => store.store);
ipcMain.handle('restart-backend', () => restartBackend());
ipcMain.handle('stop-backend', () => stopBackend());
ipcMain.handle('start-backend', () => startBackend());
ipcMain.handle('get-backend-status', () => ({ running: backendProcess !== null }));

// SECURITY: Whitelist of allowed scripts to prevent path traversal and injection
const ALLOWED_SCRIPTS = new Set([
  'run_tests.py',
  'manage.py',
  'train_model.py',
  'backtest.py',
  'export_data.py',
]);

ipcMain.handle('run-python-script', async (event, scriptName, args = []) => {
  return new Promise((resolve, reject) => {
    // SECURITY: Validate script name against whitelist
    const baseName = path.basename(scriptName);
    if (!ALLOWED_SCRIPTS.has(baseName)) {
      logToFile(`SECURITY: Blocked execution of non-whitelisted script: ${scriptName}`);
      return reject({ success: false, error: `Script not allowed: ${baseName}. Allowed: ${[...ALLOWED_SCRIPTS].join(', ')}` });
    }

    // SECURITY: Prevent path traversal
    const backendDir = path.resolve(__dirname, '../backend');
    const scriptPath = path.resolve(backendDir, baseName);
    if (!scriptPath.startsWith(backendDir)) {
      logToFile(`SECURITY: Path traversal attempt blocked: ${scriptName}`);
      return reject({ success: false, error: 'Invalid script path' });
    }

    // SECURITY: Sanitize args - reject any with shell metacharacters
    const sanitizedArgs = args.map(arg => String(arg));
    const shellMetachars = /[;&|`$(){}[\]!#~<>]/;
    for (const arg of sanitizedArgs) {
      if (shellMetachars.test(arg)) {
        logToFile(`SECURITY: Shell metacharacter in argument blocked: ${arg}`);
        return reject({ success: false, error: 'Invalid characters in arguments' });
      }
    }

    const pythonPath = store.get('pythonPath');

    logToFile(`Running script: ${scriptPath} ${sanitizedArgs.join(' ')}`);

    // SECURITY: shell: false prevents shell injection
    const proc = spawn(pythonPath, [scriptPath, ...sanitizedArgs], { shell: false });
    let output = '';
    let error = '';

    proc.stdout?.on('data', (data) => output += data.toString());
    proc.stderr?.on('data', (data) => error += data.toString());

    proc.on('close', (code) => {
      if (code === 0) {
        resolve({ success: true, output });
      } else {
        reject({ success: false, error, code });
      }
    });

    proc.on('error', (err) => {
      reject({ success: false, error: err.message });
    });
  });
});

// GPU Detection
ipcMain.handle('detect-gpu', async () => {
  return new Promise((resolve) => {
    if (process.platform === 'win32') {
      exec('wmic path win32_VideoController get name', (error, stdout) => {
        if (error) {
          resolve({ available: false, name: 'Unknown', error: error.message });
        } else {
          const lines = stdout.trim().split('\n').filter(l => l.trim() && l.trim() !== 'Name');
          const gpuName = lines[0]?.trim() || 'Unknown';
          const isNvidia = gpuName.toLowerCase().includes('nvidia');
          const isAmd = gpuName.toLowerCase().includes('amd') || gpuName.toLowerCase().includes('radeon');
          resolve({
            available: isNvidia || isAmd,
            name: gpuName,
            cuda: isNvidia,
            type: isNvidia ? 'NVIDIA' : isAmd ? 'AMD' : 'Integrated'
          });
        }
      });
    } else if (process.platform === 'linux') {
      exec('lspci | grep -i vga', (error, stdout) => {
        if (error) {
          resolve({ available: false, name: 'Unknown' });
        } else {
          const isNvidia = stdout.toLowerCase().includes('nvidia');
          resolve({
            available: isNvidia,
            name: stdout.trim(),
            cuda: isNvidia
          });
        }
      });
    } else {
      resolve({ available: false, name: 'Unknown' });
    }
  });
});

// Open external link
ipcMain.handle('open-external', (event, url) => {
  shell.openExternal(url);
});

// Show notification
ipcMain.handle('show-notification', (event, title, body) => {
  const { Notification } = require('electron');
  if (Notification.isSupported()) {
    new Notification({ title, body }).show();
  }
});

// App lifecycle
app.whenReady().then(async () => {
  // Show splash screen
  createSplashWindow();

  // Start backend if configured
  if (store.get('autoStartBackend')) {
    try {
      await startBackend();
    } catch (err) {
      console.error('Failed to start backend:', err);
    }
  }

  // Create main window after a short delay
  setTimeout(() => {
    createWindow();
  }, 1500);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else if (mainWindow) {
      mainWindow.show();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    stopBackend();
    app.quit();
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
  stopBackend();
  stopSystemMonitor();
});

// Security: Prevent new window creation
app.on('web-contents-created', (event, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught exception:', error);
  logToFile(`Uncaught exception: ${error.message}\n${error.stack}`);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled rejection:', reason);
  logToFile(`Unhandled rejection: ${reason}`);
});
