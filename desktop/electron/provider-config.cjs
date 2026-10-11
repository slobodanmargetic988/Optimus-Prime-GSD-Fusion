'use strict';
const fs = require('node:fs');
const path = require('node:path');
function prepareProvider(config, settings, directory, runtime) {
  const provider = settings.providers[config.provider];
  if (!['codex', 'openrouter'].includes(config.provider) || provider.authMode !== 'api') return {};
  const model = config.executorModel || provider.model;
  if (config.provider === 'openrouter' && !model) throw new Error('Enter an OpenRouter model ID in Settings, for example provider/model.');
  // Provider configuration contains environment variable names, never credential values.
  const target = path.join(directory, 'provider-configs', config.provider);
  fs.mkdirSync(target, {recursive: true, mode: 0o700});
  const name = config.provider === 'openrouter' ? 'OpenRouter' : 'OpenAI API';
  const baseURL = config.provider === 'openrouter' ? 'https://openrouter.ai/api/v1' : 'https://api.openai.com/v1';
  const envKey = config.provider === 'openrouter' ? 'OPENROUTER_API_KEY' : 'OPENAI_API_KEY';
  const modelLine = model ? `model = ${JSON.stringify(model)}\n` : '';
  const content = `[model_providers.optimus-api]\nname = ${JSON.stringify(name)}\nbase_url = ${JSON.stringify(baseURL)}\nenv_key = ${JSON.stringify(envKey)}\nwire_api = "responses"\nrequires_openai_auth = false\n\n[profiles.optimus-desktop]\nmodel_provider = "optimus-api"\n${modelLine}`;
  fs.writeFileSync(path.join(target, 'config.toml'), content, {mode: 0o600});
  return {environment: {CODEX_HOME: runtime.convert(target, settings)}, profile: 'optimus-desktop'};
}
module.exports = {prepareProvider};
