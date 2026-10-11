'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {randomUUID} = require('node:crypto');
const {EventEmitter} = require('node:events');
const {prepareProvider} = require('./provider-config.cjs');
const {PROVIDERS, bounded, text, readJSON, atomicJSON} = require('./store.cjs');
const ACTIVE = new Set(['preparing', 'running', 'stopping']);
const BASELINE_FILES = ['PROJECT.md', 'REQUIREMENTS.md', 'ROADMAP.md', 'STATE.md', 'STATE.json', 'PLAN_PACKETS.json', 'PLAN_CHECK.json', 'TEST_CONTRACT.md', 'PLAYWRIGHT_UAT_MATRIX.md', 'VERIFICATION.md', 'UAT.md', 'TASK_EXECUTION_STATE.json', 'PROFILE_SELECTION.json'];
const SECRET_NAMES = {codex: 'OPENAI_API_KEY', claude: 'ANTHROPIC_API_KEY', openrouter: 'OPENROUTER_API_KEY', blackbox: 'BLACKBOX_API_KEY'};
function redact(value, secrets = []) { let result = String(value); for (const key of secrets.filter(v => typeof v === 'string' && v.length >= 6).sort((a, b) => b.length - a.length)) result = result.split(key).join('[redacted]'); return result.replace(/\b(?:sk-|sk_ant_|sk-ant-)[A-Za-z0-9_-]{10,}/g, '[redacted]').replace(/((?:api[_-]?key|authorization|access[_-]?token|refresh[_-]?token)\s*[=:]\s*["']?)(?:Bearer\s+)?[^\s,"'}]+/gi, '$1[redacted]'); }
function safeRead(file, minTime = 0) { try { const stat = fs.statSync(file); if (stat.size > 8 * 1024 * 1024 || stat.mtimeMs < minTime) return {}; return readJSON(file, {}); } catch {return {};} }
function inspectPlan(projectPath) { const planning = path.join(projectPath, 'reports/optimus-prime/planning'); const state = safeRead(path.join(planning, 'STATE.json')); const check = safeRead(path.join(planning, 'PLAN_CHECK.json')); const plan = safeRead(path.join(planning, 'PLAN_PACKETS.json')); const count = Array.isArray(plan.tasks) ? plan.tasks.length : 0; const complete = BASELINE_FILES.every(name => {try {return fs.statSync(path.join(planning, name)).isFile();} catch {return false;}}); return {hasPlan: complete && state.plan_ready === true && check.passed === true && count > 0, planTaskCount: count, planId: typeof state.plan_id === 'string' ? state.plan_id : ''}; }
function validateConfig(input) {
  if (!input || !['new', 'existing', 'resume'].includes(input.mode)) throw new Error('Choose a new project, existing project or resume.');
  if (input.trustProject !== true) throw new Error('Confirm permission for agents to modify the project and execute local commands.');
  if (!PROVIDERS.includes(input.provider)) throw new Error('Choose a supported provider.');
  if (input.allowWorkerExecutorOverride === true) throw new Error('Worker provider overrides are not supported in Desktop yet. Keep all workers on the selected provider so credentials and billing stay isolated.');
  const projectPath = text(input.projectPath || '', 4096); if (!path.isAbsolute(projectPath)) throw new Error('Choose an absolute project folder.');
  const result = {useExistingPlan: input.useExistingPlan === true, expectedPlanId: input.expectedPlanId ? text(input.expectedPlanId, 500) : undefined, mode: input.mode, provider: input.provider, trustProject: true, name: text(input.name || '', 250), skipStrategy: input.skipStrategy !== false, overrideOldPlan: input.overrideOldPlan === true, resetExhaustedRetries: input.resetExhaustedRetries === true, allowWorkerExecutorOverride: input.allowWorkerExecutorOverride === true, cycleReleaseMode: input.cycleReleaseMode, projectPath: path.resolve(projectPath), mission: text(input.mission || '', 100000), scope: text(input.scope || '', 100000), workers: bounded(input.workers, 1, 10, 'Workers'), maxTasks: bounded(input.maxTasks, 1, 400, 'Task limit'), maxCycles: bounded(input.maxCycles, 1, 1000, 'Cycle limit')};
  result.command = input.command === 'plan' ? 'plan' : 'build';
  if (result.useExistingPlan && (result.mode !== 'existing' || result.command !== 'build')) throw new Error('Build this plan requires Existing project and the Build command.');
  if (result.command === 'plan' && result.mode === 'resume') throw new Error('Use Existing project to generate a new plan; Resume continues the saved build.');
  if (Array.isArray(input.files) && input.files.length > 20) throw new Error('Select at most 20 input files.');
  result.files = Array.isArray(input.files) ? input.files.slice(0, 20).map(file => { const filePath = text(file.path || '', 4096); if (!path.isAbsolute(filePath)) throw new Error('Input files must be selected from disk.'); const stat = fs.statSync(filePath); if (!stat.isFile() || stat.size > 25 * 1024 * 1024) throw new Error('Each input must be a file of at most 25 MB.'); return {path: filePath, name: path.basename(filePath), size: stat.size}; }) : [];
  if (result.files.reduce((sum, f) => sum + f.size, 0) > 100 * 1024 * 1024) throw new Error('Input files exceed the 100 MB total limit.');
  if (result.mode !== 'resume' && !result.useExistingPlan && !result.mission.trim() && !result.files.length) throw new Error('Describe the project or attach a requirements file.');
  for (const key of ['profile', 'executorModel', 'bossModel', 'bossReasoningEffort', 'runBaseSourceBranch', 'worktreesParent', 'strategyManifestFile']) if (input[key] !== undefined) result[key] = text(input[key], 4096);
  for (const key of ['worktreesParent', 'strategyManifestFile']) if (result[key] && !path.isAbsolute(result[key])) throw new Error(`${key} must be an absolute path.`);
  if (input.cycleReleaseMode && !['token_conservative', 'max_work'].includes(input.cycleReleaseMode)) throw new Error('Unknown cycle release mode.');
  if (input.selectedAliases !== undefined) result.selectedAliases = Array.isArray(input.selectedAliases) ? input.selectedAliases.map(s => text(s, 200)) : text(input.selectedAliases, 2000).split(',').map(s => s.trim()).filter(Boolean);
  if (input.constraints !== undefined) result.constraints = Array.isArray(input.constraints) ? input.constraints.map(s => text(s, 2000)) : text(input.constraints, 20000).split('\n').filter(Boolean);
  if (input.bossReasoningEffort && !['low', 'medium', 'high', 'xhigh'].includes(input.bossReasoningEffort)) throw new Error('Unknown reasoning level.');
  return result;
}
function buildPayload(config, settings, runtime, inputs) {
  const provider = settings.providers[config.provider];
  const payload = {command: config.command === 'plan' ? '/op-initialize' : config.mode === 'resume' ? '/op-resume' : '/op-build', repo_root: runtime.convert(config.projectPath, settings), max_parallel_workers: config.workers, max_plan_tasks: config.maxTasks, max_build_cycles: config.maxCycles, executor_provider: config.provider, skip_strategy: config.skipStrategy !== false, non_interactive: true, output_mode: 'json', worktrees_parent: runtime.convert(config.worktreesParent || path.join(path.dirname(config.projectPath), '.optimus-worktrees', path.basename(config.projectPath)), settings)};
  if (payload.command === '/op-build') payload.start_policy = 'new';
  if (config.mode !== 'resume' && !config.useExistingPlan) { payload.mission = config.mission.trim() || `Build the project described in the attached input files: ${inputs.join(', ')}.`; payload.scope = (config.scope.trim() || config.mission.trim() || 'Use the supplied requirements to define the project scope.') + (inputs.length ? `\n\nInput files (read these before planning):\n${inputs.map(file => `- ${file}`).join('\n')}` : ''); }
  const strings = {executor_model: config.executorModel || provider.model, profile: config.profile || provider.profile, boss_model: config.bossModel, boss_reasoning_effort: config.bossReasoningEffort, cycle_release_mode: config.cycleReleaseMode};
  for (const [key, value] of Object.entries(strings)) if (value) payload[key] = value;
  if (config.runBaseSourceBranch && config.mode !== 'resume') payload.run_base_source_branch = config.runBaseSourceBranch;
  if (config.selectedAliases?.length) payload.selected_aliases = config.selectedAliases.join(',');
  else if (config.provider === 'codex' && provider.authMode === 'subscription' && !payload.profile) payload.selected_aliases = 'codex';
  if (config.constraints?.length && !config.useExistingPlan) payload.constraints = config.constraints;
  if (config.strategyManifestFile && !config.useExistingPlan) payload.strategy_manifest_file = runtime.convert(config.strategyManifestFile, settings);
  if (config.overrideOldPlan && config.mode !== 'resume' && !config.useExistingPlan) payload.override_old_plan = true;
  if (config.allowWorkerExecutorOverride) payload.allow_worker_executor_override = true;
  if (config.resetExhaustedRetries) payload.reset_exhausted_retries = true;
  if (config.provider === 'blackbox') payload.blackbox_lane = provider.authMode === 'api' ? 'api_key' : 'free';
  return payload;
}
class Controller extends EventEmitter {
  constructor(store, runtime) { super(); this.store = store; this.runtime = runtime; this.active = null; this.starting = false; }
  async bootstrap() { const settings = this.store.settings(); return {settings, projects: this.store.state.projects, runs: this.store.state.runs, environment: await this.runtime.environment(settings, this.store.secure())}; }
  async inspectProject(raw) { const supplied = text(raw, 4096); if (!path.isAbsolute(supplied)) throw new Error('Choose an absolute project folder.'); const projectPath = path.resolve(supplied); let exists = false; try { exists = fs.statSync(projectPath).isDirectory(); } catch {} const isGit = exists && fs.existsSync(path.join(projectPath, '.git')); const hasResume = exists && fs.existsSync(path.join(projectPath, '.op-simple/current/initialize_state.json')); const plan = exists ? inspectPlan(projectPath) : {hasPlan: false, planTaskCount: 0}; const summary = !exists ? 'A new project folder will be created.' : hasResume ? 'An existing Optimus run can be resumed.' : plan.hasPlan ? 'A validated plan is ready to build.' : isGit ? 'Git repository ready to plan.' : 'Folder found. A new project requires an empty folder.'; return {path: projectPath, name: path.basename(projectPath), exists, isGit, hasResume, hasPlan: plan.hasPlan, planTaskCount: plan.planTaskCount, summary}; }
  publish(run) { this.store.run(run); this.emit('run', structuredClone(run)); }
  log(run, message, level = 'info') { run.logs.push({time: new Date().toISOString(), level, message: redact(message, this.active?.secrets || []).slice(0, 3000)}); run.logs = run.logs.slice(-200); }
  async startRun(input) {
    if (this.starting || this.active) throw new Error('A build is already active. Stop it before starting another.');
    this.starting = true;
    let run;
    try {
      const config = validateConfig(input), settings = this.store.settings(), environment = await this.runtime.environment(settings, this.store.secure());
      if (!environment.ready) throw new Error(environment.checks.filter(c => !c.ok).map(c => `${c.name}: ${c.detail}`).join('\n'));
      const available = environment.providers.find(p => p.id === config.provider); if (!available?.available) throw new Error(available?.detail || 'Provider unavailable.');
      const provider = settings.providers[config.provider], key = provider.authMode === 'api' ? this.store.secret(config.provider) || process.env[SECRET_NAMES[config.provider]] || '' : '';
      if (provider.authMode === 'api' && !key) throw new Error(`Save an API key for ${config.provider} in Settings.`);
      if (config.provider === 'openrouter' && provider.authMode !== 'api') throw new Error('OpenRouter requires API authentication.');
      const providerConfig = prepareProvider(config, settings, this.store.directory, this.runtime);
      const project = await this.inspectProject(config.projectPath);
      if (config.mode === 'new' && project.exists && fs.readdirSync(project.path).filter(name => name !== '.DS_Store').length) throw new Error('Choose an empty folder for a new project. Existing files will not be overwritten.');
      if (config.mode !== 'new' && !project.isGit) throw new Error('Choose an existing Git repository or use New project with an empty folder.');
      if (config.mode === 'resume' && !project.hasResume) throw new Error('This folder has no Optimus run to resume.');
      if (config.mode === 'existing' && project.hasResume && !config.overrideOldPlan && !config.useExistingPlan) throw new Error('This project has saved build state. Select Resume, or explicitly enable Replace plan in advanced settings.');
      if (config.useExistingPlan) { const plan = inspectPlan(project.path); if (!plan.hasPlan) throw new Error('The saved plan is incomplete or has not passed validation. Generate and validate a plan first.'); if (plan.planTaskCount > config.maxTasks) throw new Error(`This plan has ${plan.planTaskCount} tasks, above the selected ${config.maxTasks}-task limit.`); if (config.expectedPlanId && config.expectedPlanId !== plan.planId) throw new Error('This project now contains a different plan. Review its latest plan before building.'); }
      const terminate = path.join(project.path, 'terminate_run.json'); if (fs.existsSync(terminate)) { const flag = readJSON(terminate, {}); if (this.store.state.runs.some(r => r.id === flag.desktopRunId && !ACTIVE.has(r.status))) fs.unlinkSync(terminate); else throw new Error('A stop marker exists in this project. Inspect terminate_run.json before restarting.'); }
      run = {id: randomUUID(), projectPath: project.path, name: config.name || project.name, provider: config.provider, status: 'preparing', startedAt: new Date().toISOString(), summary: 'Preparing local execution.', phase: 'Preparing', cycle: 0, tasks: {total: 0, done: 0, active: 0, blocked: 0}, workers: [], logs: [], config};
      this.active = {run, settings, secrets: [key, ...Object.entries(process.env).filter(([key]) => /TOKEN|API_KEY|SECRET/.test(key)).map(([, value]) => value)], child: null, timer: null, stopTimer: null, final: null};
      this.publish(run);
      if (config.mode === 'new') {fs.mkdirSync(project.path, {recursive: true}); await this.runtime.git(settings, project.path, ['init', '-b', 'main']);}
      for (const [field, fallback] of [['user.name', 'Optimus Desktop'], ['user.email', 'optimus@localhost']]) { let value = ''; try {value = (await this.runtime.git(settings, project.path, ['config', '--get', field])).stdout.trim();} catch (error) {if (error.code !== 1) throw error;} if (!value) {await this.runtime.git(settings, project.path, ['config', '--local', field, fallback]); this.log(run, `Set repository-local Git ${field} to ${fallback}; no global identity was configured.`);} }
      if (config.mode === 'new') {fs.writeFileSync(path.join(project.path, 'README.md'), `# ${config.name || project.name}\n\n${config.mission || 'Created with Optimus Desktop.'}\n`, {flag: 'wx'}); await this.runtime.git(settings, project.path, ['add', '--', 'README.md']); await this.runtime.git(settings, project.path, ['-c', 'commit.gpgsign=false', 'commit', '-m', 'Initialize project']);}
      if (run.status === 'stopping') throw new Error('Run stopped during preparation.');
      const inputs = []; if (config.mode !== 'resume' && !config.useExistingPlan) { for (let i = 0; i < config.files.length; i++) {const file = config.files[i]; const target = path.join(project.path, '.optimus-desktop', 'inputs', run.id, `${i + 1}-${file.name}`); fs.mkdirSync(path.dirname(target), {recursive: true}); const resolvedRoot = fs.realpathSync(project.path); if (!fs.realpathSync(path.dirname(target)).startsWith(resolvedRoot + path.sep)) throw new Error('Input directory points outside the project.'); fs.copyFileSync(file.path, target, fs.constants.COPYFILE_EXCL); inputs.push(this.runtime.convert(target, settings));} }
      const payload = buildPayload(config, settings, this.runtime, inputs);
      if (providerConfig.profile) {payload.profile = providerConfig.profile; payload.codex_profile = providerConfig.profile; delete payload.selected_aliases;}
      const environmentVars = {...providerConfig.environment, OP_EXECUTOR_LOG_ROOT: this.runtime.convert(path.join(this.store.directory, 'executor-logs'), settings), OP_THREAD_DISPATCH_SCRIPT: this.runtime.convert(path.join(this.runtime.root, 'skills/thread-dispatch/scripts/dispatch_codex_run.py'), settings), OP_WORKSTATION_PREPARE_SCRIPT: this.runtime.convert(path.join(this.runtime.root, 'skills/workstation-preparation/scripts/prepare_workstation.py'), settings)};
      if (key) environmentVars[SECRET_NAMES[config.provider]] = key;
      const entrypoint = this.runtime.convert(path.join(this.runtime.root, 'scripts/op/opctl.py'), settings);
      if (run.status === 'stopping') throw new Error('Run stopped during preparation.');
      // LLM interaction classification: reasoning_effort=requires_input_classification, tooling_effort=requires_input_classification. The engine owns classification and routing of its individual LLM steps.
      const child = this.runtime.launch(settings, {runId: run.id, entrypoint, payload, environment: environmentVars});
      this.active.child = child;
      for (const [stream, level] of [[child.stdout, 'info'], [child.stderr, 'error']]) { let buffer = '', discard = false; stream.on('data', chunk => {buffer += chunk.toString(); let end; while ((end = buffer.indexOf('\n')) >= 0) { const line = buffer.slice(0, end); buffer = buffer.slice(end + 1); if (!discard) this.consumeLine(run, line, level); discard = false; } if (buffer.length > 1024 * 1024) {buffer = ''; discard = true;} }); stream.on('end', () => { if (buffer && !discard) this.consumeLine(run, buffer, level); }); }
      child.on('error', error => {this.log(run, error.message, 'error'); this.finish(run, null, error.message);});
      child.on('close', code => this.finish(run, code));
      run.status = 'running'; run.phase = config.mode === 'resume' ? 'Resuming' : config.useExistingPlan ? 'Starting build' : 'Planning'; run.summary = 'Engine running locally. Progress appears as the engine records it.';
      this.active.timer = setInterval(() => this.poll(run), 1500); this.active.timer.unref?.();
      this.store.project({...project, exists: true, isGit: true, lastOpened: run.startedAt}); this.log(run, `Started ${config.command === 'plan' ? 'planning' : 'build'} with ${config.workers} worker slots and a ${config.maxTasks}-task plan limit.`); this.publish(run); return structuredClone(run);
    } catch (error) { if (run) {run.status = run.status === 'stopping' ? 'stopped' : 'failed'; run.phase = run.status === 'stopped' ? 'Stopped' : 'Failed'; run.summary = redact(error.message, this.active?.secrets || []); run.endedAt = new Date().toISOString(); this.publish(run);} clearInterval(this.active?.timer); clearTimeout(this.active?.stopTimer); this.active = null; throw new Error(redact(error.message)); } finally { this.starting = false; }
  }
  consumeLine(run, line, level) { if (!line.trim()) return; try {const parsed = JSON.parse(line); if (parsed && typeof parsed.status === 'string' && typeof parsed.ok === 'boolean') { if (this.active?.run.id === run.id) this.active.final = parsed; this.log(run, parsed.summary || parsed.status, parsed.ok ? 'info' : 'error'); for (const error of (Array.isArray(parsed.errors) ? parsed.errors : []).slice(0, 20)) this.log(run, `${error.code || 'Error'}: ${error.message || ''}`, 'error'); for (const warning of (Array.isArray(parsed.warnings) ? parsed.warnings : []).slice(0, 10)) this.log(run, `${warning.code || 'Notice'}: ${warning.message || ''}`); if (parsed.next_action) this.log(run, parsed.next_action); return;} } catch {} this.log(run, line, level); }
  poll(run) {
    if (!this.active || this.active.run.id !== run.id) return;
    const root = path.join(run.projectPath, '.op-simple/current'); const cutoff = run.config.mode === 'resume' ? 0 : Date.parse(run.startedAt); const summary = safeRead(path.join(root, 'cycle_summary.json'), cutoff); const tasks = safeRead(path.join(root, 'task_execution_state.json'), cutoff); const workers = safeRead(path.join(root, 'worker_registry.json'), cutoff); const counts = summary.task_counts;
    if (Array.isArray(tasks.tasks) && tasks.tasks.length) { const rows = tasks.tasks; run.tasks = {total: rows.length, done: rows.filter(t => ['done', 'completed'].includes(t.status)).length, active: rows.filter(t => ['in_progress', 'running'].includes(t.status)).length, blocked: rows.filter(t => t.status === 'blocked').length}; } else if (counts) { const number = value => Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0; run.tasks = {total: ['pending', 'in_progress', 'done', 'blocked'].reduce((sum, key) => sum + number(counts[key]), 0), done: number(counts.done), active: number(counts.in_progress), blocked: number(counts.blocked)}; }
    if (run.tasks.total === 0 || run.config.command === 'plan') { const plan = safeRead(path.join(run.projectPath, 'reports/optimus-prime/planning/PLAN_PACKETS.json'), run.config.useExistingPlan ? 0 : cutoff); if (Array.isArray(plan.tasks)) run.tasks = {total: plan.tasks.length, done: 0, active: 0, blocked: 0}; }
    run.cycle = Number(summary.cycle_number) || 0; if (run.cycle) run.phase = run.status === 'stopping' ? 'Stopping' : 'Building';
    if (Array.isArray(workers.workers)) run.workers = workers.workers.slice(0, 30).map(w => ({id: String(w.worker_id || w.id || ''), status: String(w.status || w.current_status || 'idle'), task: String(w.current_task_id || w.task_id || '')}));
    if (summary.insurmountable_blocker) run.summary = 'The engine reported a blocker. Review the activity log.';
    this.publish(run);
  }
  finish(run, code, message) {
    if (!this.active || this.active.run.id !== run.id) return;
    this.poll(run); const active = this.active; clearInterval(active.timer); clearTimeout(active.stopTimer);
    if (run.config.command === 'plan' && active.final?.ok === true) run.planId = inspectPlan(run.projectPath).planId || undefined;
    run.resumeAvailable = fs.existsSync(path.join(run.projectPath, '.op-simple/current/initialize_state.json'));
    if (run.status === 'stopping') {run.status = 'stopped'; run.summary = run.resumeAvailable ? 'Stopped. Saved engine state is available for resume.' : 'Stopped before a resumable build was created. Use Existing project to start again.';}
    else if (active.final?.status?.startsWith('blocked')) {run.status = 'blocked'; run.summary = active.final.summary || 'The engine needs attention.';}
    else if (message || code !== 0) {run.status = 'failed'; run.summary = message || active.final?.summary || `The engine exited with status ${code}. Review the activity log.`;}
    else if (active.final?.ok === false) {run.status = 'failed'; run.summary = active.final.summary || 'The engine needs attention.';}
    else if (active.final?.ok === true && (active.final?.data?.stop_reason === 'project_done' || run.config.command === 'plan')) {run.status = 'completed'; run.summary = active.final?.summary || 'Project completed.';}
    else {run.status = 'stopped'; run.summary = active.final?.summary || 'The engine exited. Review saved state before resuming.';}
    run.summary = redact(run.summary, active.secrets); run.phase = run.status[0].toUpperCase() + run.status.slice(1); run.endedAt = new Date().toISOString(); const project = this.store.state.projects.find(p => p.path === run.projectPath); if (project) this.store.project({...project, hasResume: run.resumeAvailable, ...inspectPlan(run.projectPath)}); this.active = null; this.publish(run);
  }
  async stopRun(id) { const active = this.active; if (!active || active.run.id !== id) throw new Error('That run is not active.'); if (active.run.status === 'stopping') return; active.run.status = 'stopping'; active.run.phase = 'Stopping'; active.run.summary = 'Stopping the engine and its worker processes.'; atomicJSON(path.join(active.run.projectPath, 'terminate_run.json'), {desktopRunId: id, requestedAt: new Date().toISOString()}); this.publish(active.run); try {await this.runtime.stop(active.settings, id);} catch (error) {this.log(active.run, `Could not signal all workers: ${error.message}`, 'error'); if (active.child?.pid && process.platform !== 'win32') {try {process.kill(-active.child.pid, 'SIGTERM');} catch {}}} active.stopTimer = setTimeout(async () => {try {await this.runtime.stop(active.settings, id, true);} catch {} active.child?.kill('SIGKILL');}, 5000); active.stopTimer.unref?.(); }
}
module.exports = {Controller, buildPayload, validateConfig, redact, inspectPlan, BASELINE_FILES, ACTIVE};
