'use strict';

// Runs only inside the disposable CI editor, against the real Python extension.
const vscode = require('vscode');
const fs = require('fs');

exports.activate = async function () {
    const marker = process.env.GIT_REVIEW_PYTHON_TEST_MARKER;
    if (!marker) return;
    const stage = message => fs.writeFileSync(marker + '.stage', message);
    try {
        stage('activating Python');
        const extension = vscode.extensions.getExtension('ms-python.python');
        const python = await extension.activate();
        stage('waiting for Python API');
        await python.ready;
        const [folder] = vscode.workspace.workspaceFolders;
        const readSelection = async () => {
            const selected = python.environments.getActiveEnvironmentPath(folder.uri);
            const resolved = await python.environments.resolveEnvironment(selected);
            return {
                path: selected.path,
                executable: resolved?.executable?.uri?.fsPath,
                execCommand: python.settings.getExecutionDetails(folder.uri).execCommand,
            };
        };
        stage('reading initial selection');
        const initial = await readSelection();
        // Discovery refresh must not revert the selected interpreter to global Python.
        stage('refreshing environments');
        await python.environments.refreshEnvironments({forceRefresh: true});
        const refreshed = await readSelection();
        fs.writeFileSync(marker, JSON.stringify({initial, refreshed}));
    } catch (error) {
        fs.writeFileSync(marker, JSON.stringify({error: String(error)}));
    }
};
