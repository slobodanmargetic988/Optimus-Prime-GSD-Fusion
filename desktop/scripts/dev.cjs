'use strict';
const {spawn} = require('node:child_process');
const electron = require('electron');
const path = require('node:path');
const child = spawn(electron, [path.resolve(__dirname, '..')], {stdio: 'inherit', env: {...process.env, OPTIMUS_DEV_URL: process.env.OPTIMUS_DEV_URL || 'http://127.0.0.1:5173'}});
child.on('exit', code => {process.exitCode = code || 0;});
child.on('error', error => {console.error(error.message); process.exitCode = 1;});
