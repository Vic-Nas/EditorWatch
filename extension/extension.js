const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const https = require('https');
const http = require('http');

let db, currentAssignment, statusBarItem;

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

// Simple in-memory database using JSON
class SimpleDB {
    constructor() {
        this.events = [];
    }

    prepare(query) {
        return {
            run: (...params) => {
                if (query.includes('INSERT INTO events')) {
                    this.events.push({
                        id: this.events.length + 1,
                        timestamp: params[0],
                        type: params[1],
                        file: params[2],
                        char_count: params[3]
                    });
                }
            },
            all: () => {
                return this.events;
            }
        };
    }

    exec(query) {
        // No-op for CREATE TABLE
    }

    close() {
        this.events = [];
    }
}

function activate(context) {
    console.log('EditorWatch extension is now active!');
    
    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    context.subscriptions.push(statusBarItem);
    
    // Check for assignment immediately and on workspace change
    checkForAssignment(context);
    
    // Watch for .editorwatch file changes
    const watcher = vscode.workspace.createFileSystemWatcher('**/.editorwatch');
    watcher.onDidCreate(() => checkForAssignment(context));
    watcher.onDidChange(() => checkForAssignment(context));
    context.subscriptions.push(watcher);
    
    // Track document changes
    vscode.workspace.onDidChangeTextDocument(event => {
        if (currentAssignment && shouldTrackFile(event.document.fileName)) {
            logEvent(event);
        }
    });
    
    // Track saves
    vscode.workspace.onDidSaveTextDocument(doc => {
        if (currentAssignment && shouldTrackFile(doc.fileName)) {
            logSaveEvent(doc.fileName);
        }
    });
    
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
                    'EditorWatch: No assignment detected. Add a .editorwatch file to your project.'
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
    const editorwatchPath = path.join(workspaceRoot, '.editorwatch');
    
    console.log('EditorWatch: Checking for config at:', editorwatchPath);
    
    if (!fs.existsSync(editorwatchPath)) {
        console.log('EditorWatch: No .editorwatch file found');
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
    
    // Check if already accepted
    const accepted = context.globalState.get('accepted_assignments', {});
    
    if (accepted[config.assignment_id]) {
        console.log('EditorWatch: Assignment already accepted, starting monitoring');
        startMonitoring(config, context);
        return;
    }
    
    // Show opt-in prompt
    showOptInPrompt(config, context);
}

function showOptInPrompt(config, context) {
    const message = `EditorWatch detected assignment: "${config.name}"\n\n` +
                   `Course: ${config.course}\n` +
                   `Deadline: ${new Date(config.deadline).toLocaleString()}\n\n` +
                   `This will track your coding process for academic integrity.\n` +
                   `Enable monitoring?`;
    
    vscode.window.showInformationMessage(
        message,
        { modal: true },
        'Enable', 'Learn More', 'Not Now'
    ).then(async selection => {
        if (selection === 'Enable') {
            // Ask for access code
            const code = await vscode.window.showInputBox({
                prompt: 'Enter your access code (sent via email)',
                placeHolder: 'ABC123',
                ignoreFocusOut: true,
                validateInput: (text) => {
                    if (!text || text.trim().length === 0) {
                        return 'Access code is required';
                    }
                    return null;
                }
            });
            
            if (!code) {
                vscode.window.showWarningMessage('EditorWatch: Code required to enable monitoring');
                return;
            }
            
            // Store code with assignment
            config.student_code = code.trim().toUpperCase();
            
            const accepted = context.globalState.get('accepted_assignments', {});
            accepted[config.assignment_id] = {
                accepted_at: Date.now(),
                workspace: vscode.workspace.workspaceFolders[0].uri.fsPath,
                code: config.student_code
            };
            context.globalState.update('accepted_assignments', accepted);
            startMonitoring(config, context);
            
            vscode.window.showInformationMessage(
                '✅ EditorWatch monitoring enabled! Click the eye icon in the status bar to submit.'
            );
        } else if (selection === 'Learn More') {
            vscode.env.openExternal(vscode.Uri.parse('https://github.com/Vic-Nas/EditorWatch'));
        }
    });
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
        // Use simple in-memory database
        db = new SimpleDB();
        console.log('EditorWatch: Database initialized');
    } catch (error) {
        vscode.window.showErrorMessage(`EditorWatch: Database error - ${error.message}`);
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

function logEvent(event) {
    if (!db) return;
    
    const change = event.contentChanges[0];
    if (!change) return;
    
    try {
        const type = change.text ? 'insert' : 'delete';
        const charCount = Math.abs(change.text?.length || change.rangeLength || 0);
        
        db.prepare(`
            INSERT INTO events (timestamp, type, file, char_count)
            VALUES (?, ?, ?, ?)
        `).run(Date.now(), type, event.document.fileName, charCount);
    } catch (error) {
        console.error('EditorWatch: Error logging event:', error);
    }
}

function logSaveEvent(fileName) {
    if (!db) return;
    
    try {
        db.prepare(`
            INSERT INTO events (timestamp, type, file, char_count)
            VALUES (?, ?, ?, ?)
        `).run(Date.now(), 'save', fileName, 0);
    } catch (error) {
        console.error('EditorWatch: Error logging save:', error);
    }
}

async function submitAssignment(context) {
    if (!currentAssignment || !db) {
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
            const events = db.prepare('SELECT * FROM events ORDER BY timestamp').all();
            
            if (events.length === 0) {
                vscode.window.showWarningMessage('No coding activity detected. Write some code first!');
                return;
            }
            
            progress.report({ message: 'Uploading...' });
            
            const payload = JSON.stringify({
                code: currentAssignment.student_code,
                assignment_id: currentAssignment.assignment_id,
                events: events
            });
            
            await makeRequest(currentAssignment.server + '/api/submit', payload);
            
            vscode.window.showInformationMessage(
                '✅ Assignment submitted successfully!',
                'OK'
            );
            
            // Clean up
            if (db) {
                db.close();
                db = null;
            }
            statusBarItem.hide();
            currentAssignment = null;
            
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
            
            if (db) {
                db.close();
                db = null;
            }
            
            currentAssignment = null;
            statusBarItem.hide();
            
            vscode.window.showInformationMessage('EditorWatch monitoring disabled');
        }
    });
}

function deactivate() {
    if (db) {
        try {
            db.close();
        } catch (error) {
            console.error('EditorWatch: Error closing database:', error);
        }
    }
}

module.exports = {
    activate,
    deactivate
};