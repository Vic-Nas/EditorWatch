const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const https = require('https');
const http = require('http');
const { EventTracker } = require('./tracker');

let tracker, currentAssignment, statusBarItem;

// Patterns to always ignore
const IGNORE_PATTERNS = [
    '__pycache__',
    '.git',
    '.history',
    'node_modules',
    '.vscode',
    '.idea',
    'venv',
    'env',
    '.env',
    'dist',
    'build',
    '.cache'
];

function activate(context) {
    console.log('EditorWatch extension is now active!');
    
    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    context.subscriptions.push(statusBarItem);
    
    // Check for assignment immediately and on workspace change
    checkForAssignment(context);
    
    // Watch for editorwatch file changes
    const watcher = vscode.workspace.createFileSystemWatcher('**/editorwatch');
    watcher.onDidCreate(() => checkForAssignment(context));
    watcher.onDidChange(() => checkForAssignment(context));
    context.subscriptions.push(watcher);
    
    // Track document changes - PROPERLY DISPOSED
    const docChangeDisposable = vscode.workspace.onDidChangeTextDocument(event => {
        if (currentAssignment && shouldTrackFile(event.document.fileName)) {
            tracker.trackChange(event);  // ← USE TRACKER
        }
    });
    context.subscriptions.push(docChangeDisposable);
    
    // Track saves - PROPERLY DISPOSED
    const saveDisposable = vscode.workspace.onDidSaveTextDocument(doc => {
        if (currentAssignment && shouldTrackFile(doc.fileName)) {
            tracker.trackSave(doc.fileName);  // ← USE TRACKER
        }
    });
    context.subscriptions.push(saveDisposable);
    
    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('editorwatch.submit', () => submitAssignment(context))
    );
    
    context.subscriptions.push(
        vscode.commands.registerCommand('editorwatch.disable', () => disableMonitoring(context))
    );
    
    context.subscriptions.push(
        vscode.commands.registerCommand('editorwatch.status', () => {
            if (currentAssignment) {
                vscode.window.showInformationMessage(
                    `EditorWatch is monitoring: ${currentAssignment.name}`
                );
            } else {
                vscode.window.showInformationMessage(
                    'EditorWatch: No assignment detected. Add an editorwatch file to your project.'
                );
            }
        })
    );
}

function checkForAssignment(context) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
        console.log('EditorWatch: No workspace folder open');
        return;
    }
    
    const workspaceRoot = workspaceFolders[0].uri.fsPath;
    const editorwatchPath = path.join(workspaceRoot, 'editorwatch');
    
    console.log('EditorWatch: Checking for config at:', editorwatchPath);
    
    if (!fs.existsSync(editorwatchPath)) {
        console.log('EditorWatch: No editorwatch file found');
        return;
    }
    
    console.log('EditorWatch: Config file found!');
    
    let config;
    try {
        const configContent = fs.readFileSync(editorwatchPath, 'utf8');
        config = JSON.parse(configContent);
        console.log('EditorWatch: Config loaded:', config);
    } catch (error) {
        vscode.window.showErrorMessage(`EditorWatch: Invalid config file - ${error.message}`);
        return;
    }
    
    // Check deadline
    if (new Date() > new Date(config.deadline)) {
        vscode.window.showWarningMessage('EditorWatch: Assignment deadline has passed');
        return;
    }
    
    // Start monitoring immediately (do not ask for code at startup).
    // Code will be requested only at submit time if missing or invalid.
    console.log('EditorWatch: Starting monitoring without startup prompt');
    startMonitoring(config, context);
}

function startMonitoring(config, context) {
    // Restore code if it was saved
    if (!config.student_code) {
        const accepted = context.globalState.get('accepted_assignments', {});
        const savedData = accepted[config.assignment_id];
        if (savedData && savedData.code) {
            config.student_code = savedData.code;
        }
    }
    
    currentAssignment = config;
    
    try {
        // Initialize the tracker
        tracker = new EventTracker();
        console.log('EditorWatch: Tracker initialized');
    } catch (error) {
        vscode.window.showErrorMessage(`EditorWatch: Tracker error - ${error.message}`);
        return;
    }
    
    // Show status bar
    statusBarItem.text = `$(eye) EditorWatch: ${config.name.substring(0, 20)}`;
    statusBarItem.tooltip = `Monitoring: ${config.name}\nClick to submit`;
    statusBarItem.command = 'editorwatch.submit';
    statusBarItem.show();
    
    vscode.window.showInformationMessage(`EditorWatch: Now monitoring "${config.name}"`);
}

function shouldTrackFile(fileName) {
    if (!currentAssignment) return false;
    
    const relativePath = vscode.workspace.asRelativePath(fileName);
    
    // Check if in ignored directory
    for (const ignore of IGNORE_PATTERNS) {
        if (relativePath.includes(ignore)) {
            return false;
        }
    }
    
    const patterns = currentAssignment.track_patterns || ['*.py'];
    const baseName = path.basename(fileName);
    
    return patterns.some(pattern => {
        // Convert glob pattern to regex
        const regex = new RegExp('^' + pattern.replace(/\./g, '\\.').replace(/\*/g, '.*') + '$');
        return regex.test(baseName);
    });
}

async function submitAssignment(context) {
    if (!currentAssignment || !tracker) {
        vscode.window.showErrorMessage('EditorWatch: No active assignment');
        return;
    }
    
    // Check deadline again before submission
    if (new Date() > new Date(currentAssignment.deadline)) {
        vscode.window.showErrorMessage(
            '⏰ Deadline has passed! Your work is saved locally but cannot be submitted.'
        );
        return;
    }
    
    const answer = await vscode.window.showWarningMessage(
        `Submit "${currentAssignment.name}"?\n\nThis will upload your coding timeline for analysis.`,
        { modal: true },
        'Submit', 'Cancel'
    );
    
    if (answer !== 'Submit') return;
    
    await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: 'Submitting to EditorWatch...',
        cancellable: false
    }, async (progress) => {
        try {
            progress.report({ message: 'Collecting events...' });
            const compactData = tracker.getEvents();  // Get compact format
            
            if (compactData.events.length === 0) {
                vscode.window.showWarningMessage('No coding activity detected. Write some code first!');
                return;
            }
            
            progress.report({ message: 'Collecting files...' });

            // Build map of filename -> contents for files touched in events
            const filesMap = {};
            const uniqueFiles = Array.from(new Set(
                compactData.events.map(e => e[2]).filter(Boolean)  // e[2] is filename
            ));

            for (const fpath of uniqueFiles) {
                const base = path.basename(fpath);
                let content = '';
                try {
                    // Try reading from disk first
                    content = fs.readFileSync(fpath, 'utf8');
                } catch (err) {
                    try {
                        // Fallback to opening via VS Code API
                        const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(fpath));
                        content = doc.getText();
                    } catch (err2) {
                        content = '';
                    }
                }
                filesMap[base] = content;
            }

            progress.report({ message: 'Uploading...' });

            // Ensure we have a student access code. If missing, ask now.
            if (!currentAssignment.student_code) {
                const codeInput = await vscode.window.showInputBox({
                    prompt: 'Enter your access code (sent via email)',
                    placeHolder: 'ABC123',
                    ignoreFocusOut: true,
                    validateInput: (text) => {
                        if (!text || text.trim().length === 0) return 'Access code is required';
                        return null;
                    }
                });

                if (!codeInput) {
                    vscode.window.showWarningMessage('Submission cancelled: access code required');
                    return;
                }

                currentAssignment.student_code = codeInput.trim().toUpperCase();
                // persist the code so user doesn't need to re-enter frequently
                const accepted = context.globalState.get('accepted_assignments', {});
                accepted[currentAssignment.assignment_id] = accepted[currentAssignment.assignment_id] || {};
                accepted[currentAssignment.assignment_id].code = currentAssignment.student_code;
                context.globalState.update('accepted_assignments', accepted);
            }

            const payload = JSON.stringify({
                code: currentAssignment.student_code,
                assignment_id: currentAssignment.assignment_id,
                base_time: compactData.base_time,
                events: compactData.events,
                files: filesMap
            });

            // attempt submission; on failure offer to re-enter code then retry
            try {
                await makeRequest(currentAssignment.server + '/api/submit', payload);
            } catch (err) {
                // Ask user if they'd like to enter a different code (likely invalid)
                const choice = await vscode.window.showErrorMessage(
                    `Submission failed: ${err.message}`,
                    'Enter Code', 'Retry', 'Cancel'
                );

                if (choice === 'Enter Code') {
                    const newCode = await vscode.window.showInputBox({
                        prompt: 'Enter your access code (sent via email)',
                        placeHolder: 'ABC123',
                        ignoreFocusOut: true,
                        validateInput: (text) => {
                            if (!text || text.trim().length === 0) return 'Access code is required';
                            return null;
                        }
                    });
                    if (newCode) {
                        currentAssignment.student_code = newCode.trim().toUpperCase();
                        const accepted = context.globalState.get('accepted_assignments', {});
                        accepted[currentAssignment.assignment_id] = accepted[currentAssignment.assignment_id] || {};
                        accepted[currentAssignment.assignment_id].code = currentAssignment.student_code;
                        context.globalState.update('accepted_assignments', accepted);
                        // retry once
                        await makeRequest(currentAssignment.server + '/api/submit', JSON.stringify({
                            code: currentAssignment.student_code,
                            assignment_id: currentAssignment.assignment_id,
                            base_time: compactData.base_time,
                            events: compactData.events,
                            files: filesMap
                        }));
                        vscode.window.showInformationMessage('✅ Assignment submitted successfully after code update!');
                    } else {
                        vscode.window.showWarningMessage('Submission cancelled');
                    }
                } else if (choice === 'Retry') {
                    await makeRequest(currentAssignment.server + '/api/submit', payload);
                    vscode.window.showInformationMessage('✅ Assignment submitted successfully!');
                } else {
                    vscode.window.showWarningMessage('Submission cancelled');
                }
            }
            
            vscode.window.showInformationMessage(
                '✅ Assignment submitted successfully!',
                'OK'
            );
            
            // Keep monitoring active so users can resubmit until deadline
            
        } catch (error) {
            vscode.window.showErrorMessage(
                `Submission failed: ${error.message}`,
                'Retry'
            ).then(selection => {
                if (selection === 'Retry') {
                    submitAssignment(context);
                }
            });
        }
    });
}

function makeRequest(url, data) {
    return new Promise((resolve, reject) => {
        try {
            const urlObj = new URL(url);
            const protocol = urlObj.protocol === 'https:' ? https : http;
            
            const options = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(data)
                }
            };
            
            const req = protocol.request(url, options, res => {
                let body = '';
                res.on('data', chunk => body += chunk);
                res.on('end', () => {
                    if (res.statusCode >= 200 && res.statusCode < 300) {
                        resolve(body);
                    } else {
                        reject(new Error(`Server returned ${res.statusCode}: ${body}`));
                    }
                });
            });
            
            req.on('error', reject);
            req.setTimeout(30000, () => {
                req.destroy();
                reject(new Error('Request timeout'));
            });
            
            req.write(data);
            req.end();
        } catch (error) {
            reject(error);
        }
    });
}

function disableMonitoring(context) {
    if (!currentAssignment) {
        vscode.window.showInformationMessage('EditorWatch: No active monitoring');
        return;
    }
    
    vscode.window.showWarningMessage(
        'Disable EditorWatch monitoring? You will need to re-enable it to submit.',
        'Disable', 'Cancel'
    ).then(selection => {
        if (selection === 'Disable') {
            const accepted = context.globalState.get('accepted_assignments', {});
            delete accepted[currentAssignment.assignment_id];
            context.globalState.update('accepted_assignments', accepted);
            
            if (tracker) {
                tracker.clear();
                tracker = null;
            }
            
            currentAssignment = null;
            statusBarItem.hide();
            
            vscode.window.showInformationMessage('EditorWatch monitoring disabled');
        }
    });
}

function deactivate() {
    if (tracker) {
        try {
            tracker.clear();
        } catch (error) {
            console.error('EditorWatch: Error closing tracker:', error);
        }
    }
}

module.exports = {
    activate,
    deactivate
};