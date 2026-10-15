'use strict';

const vscode = require('vscode');

const EMPTY_SCHEME = 'git-review-empty';
const GIT_EXTENSION = 'vscode.git';
const REPOSITORY_TIMEOUT_MS = 30000;

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function findReviewRepository(api, folder) {
    const deadline = Date.now() + REPOSITORY_TIMEOUT_MS;
    while (Date.now() < deadline) {
        // Match the review worktree, never an unrelated repository or parent.
        const repository = api.repositories.find(
            candidate => candidate.rootUri.fsPath === folder.uri.fsPath,
        );
        if (repository) {
            // Initial discovery can report an empty change list. An explicit
            // status refresh makes the first snapshot deterministic.
            await repository.status();
            return repository;
        }
        await sleep(250);
    }
    throw new Error('Git did not discover the review worktree');
}

function diffEntries(repository, api, folder) {
    const entries = [
        ...repository.state.workingTreeChanges,
        ...repository.state.untrackedChanges,
        ...repository.state.indexChanges,
    ];
    const seen = new Set();
    const root = folder.uri.fsPath;
    return entries.flatMap(change => {
        const modified = change.uri;
        const relative = require('path').relative(root, modified.fsPath);
        // Avoid opening changes belonging to a different repository.
        if (relative === '..' || relative.startsWith('..' + require('path').sep) ||
            require('path').isAbsolute(relative) || seen.has(modified.toString())) {
            return [];
        }
        seen.add(modified.toString());

        // Git status 7 = untracked, 1 = index-added. Neither exists in HEAD.
        // Git status 6 = deleted, 2 = index-deleted. They have no working file.
        // A blank virtual document produces a real red/green diff even for
        // additions and deletions, rather than a missing-file editor.
        const added = change.status === 7 || change.status === 1;
        const deleted = change.status === 6 || change.status === 2;
        const original = added
            ? vscode.Uri.from({scheme: EMPTY_SCHEME, path: modified.path})
            : api.toGitUri(change.originalUri || modified, 'HEAD');
        const current = deleted
            ? vscode.Uri.from({scheme: EMPTY_SCHEME, path: modified.path})
            : modified;
        return [{original, current, label: relative}];
    }).sort((a, b) => a.label.localeCompare(b.label));
}

async function openReviewDiffs(folder) {
    const extension = vscode.extensions.getExtension(GIT_EXTENSION);
    if (!extension) {
        throw new Error('Built-in Git extension is missing');
    }
    const git = await extension.activate();
    const api = git.getAPI(1);
    const repository = await findReviewRepository(api, folder);
    const entries = diffEntries(repository, api, folder);

    for (const entry of entries) {
        // No preview tabs: each file stays open and can be reached with Ctrl+Tab.
        // The right document is the actual worktree file, preserving navigation.
        await vscode.commands.executeCommand(
            'vscode.diff', entry.original, entry.current, entry.label,
            {preview: false},
        );
    }

    if (process.env.GIT_REVIEW_DIFF_TEST_MARKER) {
        const fs = require('fs');
        const tabs = await Promise.all(vscode.window.tabGroups.all.flatMap(group => group.tabs)
            .filter(tab => tab.input instanceof vscode.TabInputTextDiff)
            .map(async tab => ({
                original: tab.input.original.toString(),
                modified: tab.input.modified.toString(),
                originalText: (await vscode.workspace.openTextDocument(tab.input.original)).getText(),
                modifiedText: (await vscode.workspace.openTextDocument(tab.input.modified)).getText(),
                label: tab.label,
                preview: tab.isPreview,
            })));
        fs.writeFileSync(process.env.GIT_REVIEW_DIFF_TEST_MARKER,
            JSON.stringify({expected: entries.length, tabs}, null, 2) + '\n');
    }
}

async function activate(context) {
    if (!vscode.workspace.getConfiguration('gitReview').get('showSourceControl', false)) {
        return;
    }
    await vscode.commands.executeCommand('workbench.view.scm');
    if (process.env.GIT_REVIEW_GUI_TEST_MARKER) {
        require('fs').writeFileSync(process.env.GIT_REVIEW_GUI_TEST_MARKER, 'scm-opened\n');
    }
    if (!vscode.workspace.getConfiguration('gitReview').get('openDiffTabs', false)) {
        return;
    }
    context.subscriptions.push(vscode.workspace.registerTextDocumentContentProvider(
        EMPTY_SCHEME, {provideTextDocumentContent: () => ''},
    ));
    const [folder] = vscode.workspace.workspaceFolders || [];
    if (!folder || vscode.workspace.workspaceFolders.length !== 1) {
        return;
    }
    try {
        await openReviewDiffs(folder);
    } catch (error) {
        vscode.window.showWarningMessage('Git review: could not open all diff tabs: ' + error.message);
    }
}

function deactivate() {}
module.exports = {activate, deactivate};
