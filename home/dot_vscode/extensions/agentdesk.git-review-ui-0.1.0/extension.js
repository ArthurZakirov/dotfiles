'use strict';
const vscode = require('vscode');

async function activate() {
    if (!vscode.workspace.getConfiguration('gitReview').get('showSourceControl', false)) {
        return;
    }
    await vscode.commands.executeCommand('workbench.view.scm');
    console.log('git-review-ui: source control opened');
}

function deactivate() {}
module.exports = {activate, deactivate};
