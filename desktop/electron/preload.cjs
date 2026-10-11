'use strict';
const {contextBridge, ipcRenderer, webUtils} = require('electron');
contextBridge.exposeInMainWorld('optimus', Object.freeze({
  bootstrap: () => ipcRenderer.invoke('optimus:bootstrap'),
  chooseDirectory: () => ipcRenderer.invoke('optimus:choose-directory'),
  chooseFiles: () => ipcRenderer.invoke('optimus:choose-files'),
  filePath: file => webUtils.getPathForFile(file),
  saveSettings: settings => ipcRenderer.invoke('optimus:save-settings', settings),
  inspectProject: projectPath => ipcRenderer.invoke('optimus:inspect-project', projectPath),
  startRun: config => ipcRenderer.invoke('optimus:start-run', config),
  stopRun: id => ipcRenderer.invoke('optimus:stop-run', id),
  subscribeRun: listener => { const handler = (_event, run) => listener(run); ipcRenderer.on('optimus:run', handler); return () => ipcRenderer.removeListener('optimus:run', handler); },
  openPath: target => ipcRenderer.invoke('optimus:open-path', target),
  openExternal: url => ipcRenderer.invoke('optimus:open-external', url),
}));
