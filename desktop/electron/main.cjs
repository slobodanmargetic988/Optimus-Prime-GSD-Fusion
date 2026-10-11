'use strict';
const {app, BrowserWindow, ipcMain, dialog, safeStorage, shell} = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const {pathToFileURL} = require('node:url');
const {Store, text} = require('./store.cjs');
const {Runtime} = require('./runtime.cjs');
const {Controller} = require('./controller.cjs');
const DOCS_HOSTS = new Set(['developers.openai.com', 'learn.chatgpt.com', 'platform.openai.com', 'help.openai.com', 'code.claude.com', 'docs.anthropic.com', 'console.anthropic.com', 'openrouter.ai', 'docs.blackbox.ai', 'docs.github.com', 'git-scm.com', 'www.python.org', 'learn.microsoft.com']);
const COMMUNITY_URLS = new Set(['https://github.com/slobodanmargetic988/Optimus-Prime-GSD-Fusion', 'https://github.com/sponsors/slobodanmargetic988']);
if (!app.isPackaged && process.env.OPTIMUS_USER_DATA) app.setPath('userData', path.resolve(process.env.OPTIMUS_USER_DATA));
let window, controller, store, quitting = false, closeRequested = false;
const previewURL = !app.isPackaged ? process.env.OPTIMUS_DEV_URL : null;
if (previewURL) { const parsed = new URL(previewURL); if (parsed.protocol !== 'http:' || !['localhost', '127.0.0.1'].includes(parsed.hostname)) throw new Error('The development URL must use localhost.'); }
const documentURL = previewURL ? new URL(previewURL).href : pathToFileURL(path.join(__dirname, '../dist/index.html')).href;
function trusted(event) { if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || event.senderFrame.url.split('#')[0] !== documentURL.split('#')[0]) throw new Error('Untrusted desktop request.'); }
function register(channel, handler) { ipcMain.handle(`optimus:${channel}`, (event, ...args) => {trusted(event); return handler(...args);}); }
function setupIPC() {
  register('bootstrap', () => controller.bootstrap());
  register('choose-directory', async () => {const result = await dialog.showOpenDialog(window, {properties: ['openDirectory', 'createDirectory']}); return result.canceled ? null : result.filePaths[0];});
  register('choose-files', async () => {const result = await dialog.showOpenDialog(window, {properties: ['openFile', 'multiSelections']}); return result.canceled ? [] : result.filePaths.map(file => ({name: path.basename(file), path: file, size: fs.statSync(file).size}));});
  register('save-settings', settings => store.saveSettings(settings));
  register('inspect-project', projectPath => controller.inspectProject(projectPath));
  register('start-run', config => controller.startRun(config));
  register('stop-run', id => controller.stopRun(text(id, 100)));
  register('open-path', async raw => { const target = path.resolve(text(raw, 4096)); const allowed = [...store.state.projects.map(p => p.path), ...store.state.runs.map(r => r.projectPath), store.directory]; if (!allowed.some(root => target === root || target.startsWith(root + path.sep))) throw new Error('Only project or application folders can be opened.'); const resolved = fs.realpathSync(target); if (!fs.statSync(resolved).isDirectory()) throw new Error('Choose a folder to open.'); if (!allowed.some(root => {try {const base = fs.realpathSync(root); return resolved === base || resolved.startsWith(base + path.sep);} catch {return false;}})) throw new Error('Folder points outside the project.'); const error = await shell.openPath(resolved); if (error) throw new Error(error);});
  register('open-external', async raw => {const url = new URL(text(raw, 4096)); const approved = (DOCS_HOSTS.has(url.hostname) && !url.port) || COMMUNITY_URLS.has(url.href); if (url.protocol !== 'https:' || !approved || url.username || url.password) throw new Error('Only approved documentation and Optimus community links can be opened.'); await shell.openExternal(url.href);});
  controller.on('run', run => {if (window && !window.isDestroyed()) window.webContents.send('optimus:run', run);});
}
function createWindow() {
  window = new BrowserWindow({width: 1440, height: 960, minWidth: 960, minHeight: 700, title: 'Optimus Desktop', backgroundColor: '#0b0e12', titleBarStyle: 'default', webPreferences: {preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true, allowRunningInsecureContent: false}});
  window.webContents.setWindowOpenHandler(() => ({action: 'deny'}));
  window.webContents.on('will-navigate', (event, url) => {if (url !== documentURL) event.preventDefault();});
  window.webContents.session.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  window.webContents.session.setPermissionCheckHandler(() => false);
  window.on('close', async event => {if (!quitting && controller.active) {event.preventDefault(); if (closeRequested) return; closeRequested = true; const response = await dialog.showMessageBox(window, {type: 'question', buttons: ['Keep building', 'Stop build and close'], defaultId: 0, cancelId: 0, message: 'A build is still running.', detail: 'Closing Optimus stops its engine and workers. You can resume the saved project later.'}); if (response.response === 1) {try {await controller.stopRun(controller.active.run.id);} catch {} await new Promise(resolve => setTimeout(resolve, 5500)); quitting = true; app.quit();} closeRequested = false;}});
  window.loadURL(documentURL);
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => {if (window) {if (window.isMinimized()) window.restore(); window.focus();}});
  app.whenReady().then(() => { const runtimeRoot = app.isPackaged ? path.join(process.resourcesPath, 'runtime') : path.resolve(__dirname, '../..'); store = new Store(app.getPath('userData'), safeStorage); controller = new Controller(store, new Runtime(runtimeRoot, {bridge: app.isPackaged ? path.join(process.resourcesPath, 'runtime/desktop/electron/runtime-bridge.py') : undefined})); setupIPC(); createWindow(); });
  app.on('activate', () => {if (BrowserWindow.getAllWindows().length === 0) createWindow();});
  app.on('before-quit', event => {if (controller?.active && !quitting) {event.preventDefault(); window?.close();}});
  app.on('window-all-closed', () => {if (process.platform !== 'darwin' || quitting) app.quit();});
}
