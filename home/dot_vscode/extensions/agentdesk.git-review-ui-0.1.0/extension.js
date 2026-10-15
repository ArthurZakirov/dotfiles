'use strict';
const vscode = require('vscode');

async function activate() {
    if (!vscode.workspace.getConfiguration('gitReview').get('showSourceControl', false)) {
        return;
    }
    await vscode.commands.executeCommand('workbench.view.scm');
    if (process.env.GIT_REVIEW_GUI_TEST_MARKER) {
        require('fs').writeFileSync(process.env.GIT_REVIEW_GUI_TEST_MARKER, 'scm-opened\n');
    }
}

function deactivate() {}
module.exports = {activate, deactivate};
