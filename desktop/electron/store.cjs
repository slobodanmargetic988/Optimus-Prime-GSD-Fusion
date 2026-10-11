'use strict';
const fs = require('node:fs');
const path = require('node:path');
const PROVIDERS = ['codex', 'claude', 'openrouter', 'blackbox'];
const DEFAULT_SETTINGS = {provider: 'codex', workers: 3, maxTasks: 40, maxCycles: 10, pythonPath: 'python3', wslDistribution: '', providers: {codex: {model: '', authMode: 'subscription', profile: ''}, claude: {model: '', authMode: 'subscription', profile: ''}, openrouter: {model: '', authMode: 'api', profile: ''}, blackbox: {model: '', authMode: 'api', profile: ''}}};
function bounded(value, low, high, label) { if (!Number.isInteger(value) || value < low || value > high) throw new Error(`${label} must be an integer from ${low} to ${high}.`); return value; }
function text(value, max = 1000) { if (typeof value !== 'string' || value.length > max || value.includes('\0')) throw new Error('Invalid text setting.'); return value; }
function atomicJSON(file, data) { fs.mkdirSync(path.dirname(file), {recursive: true, mode: 0o700}); const tmp = `${file}.tmp`; fs.writeFileSync(tmp, JSON.stringify(data, null, 2), {mode: 0o600}); fs.renameSync(tmp, file); }
function readJSON(file, fallback) { try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; } }
class Store {
  constructor(directory, safeStorage) { this.directory = directory; this.safeStorage = safeStorage; this.file = path.join(directory, 'desktop-state.json'); this.state = readJSON(this.file, {settings: structuredClone(DEFAULT_SETTINGS), secrets: {}, projects: [], runs: []}); this.state.settings = {...structuredClone(DEFAULT_SETTINGS), ...this.state.settings, providers: {...structuredClone(DEFAULT_SETTINGS.providers), ...this.state.settings?.providers}}; this.state.secrets ||= {}; this.state.projects ||= []; this.state.runs ||= []; for (const run of this.state.runs) { if (['running', 'preparing', 'stopping'].includes(run.status)) { run.status = 'interrupted'; run.summary = 'The application closed during this run. Inspect the project, then resume when its previous processes have stopped.'; } } this.persist(); }
  secure() { return !!this.safeStorage?.isEncryptionAvailable() && this.safeStorage.getSelectedStorageBackend?.() !== 'basic_text'; }
  settings() { const result = structuredClone(this.state.settings); for (const provider of PROVIDERS) { delete result.providers[provider].apiKey; result.providers[provider].hasApiKey = !!this.state.secrets[provider]; } return result; }
  saveSettings(input) {
    if (!input || !PROVIDERS.includes(input.provider)) throw new Error('Choose a supported provider.');
    const result = {provider: input.provider, workers: bounded(input.workers, 1, 10, 'Workers'), maxTasks: bounded(input.maxTasks, 1, 400, 'Task limit'), maxCycles: bounded(input.maxCycles, 1, 1000, 'Cycle limit'), pythonPath: text(input.pythonPath || 'python3'), wslDistribution: text(input.wslDistribution || ''), providers: {}};
    const secrets = {...this.state.secrets};
    for (const provider of PROVIDERS) { const incoming = input.providers?.[provider] || DEFAULT_SETTINGS.providers[provider]; if (!['api', 'subscription'].includes(incoming.authMode)) throw new Error('Invalid authentication mode.'); result.providers[provider] = {model: text(incoming.model || '', 250), authMode: incoming.authMode, profile: text(incoming.profile || '', 250)}; if (typeof incoming.apiKey === 'string') { const key = text(incoming.apiKey, 8192).trim(); if (key) { if (!this.secure()) throw new Error('Secure OS credential storage is unavailable. Enable Keychain, Credential Manager, or a Linux secret service before saving API keys.'); secrets[provider] = this.safeStorage.encryptString(key).toString('base64'); } else if (incoming.hasApiKey === false) delete secrets[provider]; } }
    this.state.settings = result; this.state.secrets = secrets; this.persist(); return this.settings();
  }
  secret(provider) { if (!this.state.secrets[provider]) return ''; if (!this.secure()) throw new Error('Unlock the operating system credential store to use your saved API key.'); try { return this.safeStorage.decryptString(Buffer.from(this.state.secrets[provider], 'base64')); } catch { throw new Error('The saved API key could not be decrypted. Save it again in Settings.'); } }
  persist() { atomicJSON(this.file, this.state); }
  project(project) { this.state.projects = [project, ...this.state.projects.filter(p => p.path !== project.path)].slice(0, 50); this.persist(); }
  run(run) { this.state.runs = [structuredClone(run), ...this.state.runs.filter(r => r.id !== run.id)].slice(0, 30); this.persist(); }
}
module.exports = {Store, DEFAULT_SETTINGS, PROVIDERS, bounded, text, atomicJSON, readJSON};
