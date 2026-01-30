const vscode = require('vscode');
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');
const https = require('https');
const http = require('http');

let db, currentAssignment, statusBarItem;

function activate(context) {
    console.log('EditorWatch extension activated');
    
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    context.subscriptions.push(statusBarItem);
    
    checkForAssignment(context);
    
    vscode.workspace.onDidChangeTextDocument(event => {
        if (currentAssignment && shouldTrackFile(event.document.fileName)) {
            logEvent(event);
        }
    });
    
    vscode.workspace.onDidSaveTextDocument(doc => {
        if (currentAssignment && shouldTrackFile(doc.fileName)) {
            logSaveEvent(doc.fileName);
        }
    });
    
    context.subscriptions.push(
        vscode.commands.registerCommand('editorwatch.submit', () => submitAssignment(context))
    );
    
    context.subscriptions.push(
        vscode.commands.registerCommand('editorwatch.disable', () => disableMonitoring(context))
    );
}

function checkForAssignment(context) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) return;
    
    const editorwatchPath = path.join(workspaceFolders[0].uri.fsPath, '.editorwatch');
    if (!fs.existsSync(editorwatchPath)) return;
    
    const config = JSON.parse(fs.readFileSync(editorwatchPath, 'utf8'));
    const accepted = context.globalState.get('accepted_assignments', {});
    
    if (new Date() > new Date(config.deadline)) {
        vscode.window.showWarningMessage('EditorWatch: Assignment deadline has passed');
        return;
    }
    
    if (accepted[config.assignment_id]) {
        startMonitoring(config, context);
        return;
    }
    
    showOptInPrompt(config, context);
}

function showOptInPrompt(config, context) {
    vscode.window.showInformationMessage(
        `Enable EditorWatch for "${config.name}"? This tracks your coding process for academic integrity.`,
        'Enable', 'Learn More', 'Decline'
    ).then(selection => {
        if (selection === 'Enable') {
            const accepted = context.globalState.get('accepted_assignments', {});
            accepted[config.assignment_id] = {
                accepted_at: Date.now(),
                workspace: vscode.workspace.workspaceFolders[0].uri.fsPath
            };
            context.globalState.update('accepted_assignments', accepted);
            startMonitoring(config, context);
        } else if (selection === 'Learn More') {
            vscode.env.openExternal(vscode.Uri.parse('https://github.com/Vic-Nas/EditorWatch'));
        }
    });
}

function startMonitoring(config, context) {
    currentAssignment = config;
    
    const dbPath = path.join(vscode.workspace.workspaceFolders[0].uri.fsPath, '.editorwatch.db');
    db = new Database(dbPath);
    
    db.exec(`
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            type TEXT,
            file TEXT,
            char_count INTEGER
        )
    `);
    
    statusBarItem.text = `$(eye) EditorWatch: ${config.name}`;
    statusBarItem.command = 'editorwatch.submit';
    statusBarItem.show();
    
    vscode.window.showInformationMessage(`EditorWatch monitoring enabled for ${config.name}`);
}

function shouldTrackFile(fileName) {
    if (!currentAssignment) return false;
    const patterns = currentAssignment.track_patterns || ['*.py'];
    return patterns.some(pattern => {
        const regex = new RegExp(pattern.replace('*', '.*'));
        return regex.test(fileName);
    });
}

function logEvent(event) {
    if (!db) return;
    
    const change = event.contentChanges[0];
    if (!change) return;
    
    const type = change.text ? 'insert' : 'delete';
    const charCount = Math.abs(change.text?.length || change.rangeLength || 0);
    
    db.prepare(`
        INSERT INTO events (timestamp, type, file, char_count)
        VALUES (?, ?, ?, ?)
    `).run(Date.now(), type, event.document.fileName, charCount);
}

function logSaveEvent(fileName) {
    if (!db) return;
    
    db.prepare(`
        INSERT INTO events (timestamp, type, file, char_count)
        VALUES (?, ?, ?, ?)
    `).run(Date.now(), 'save', fileName, 0);
}

async function submitAssignment(context) {
    if (!currentAssignment || !db) {
        vscode.window.showErrorMessage('No active EditorWatch assignment');
        return;
    }
    
    const answer = await vscode.window.showInformationMessage(
        'Submit your work to EditorWatch? This will upload your coding timeline.',
        'Submit', 'Cancel'
    );
    
    if (answer !== 'Submit') return;
    
    vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: 'Submitting to EditorWatch...'
    }, async () => {
        try {
            // Collect required student info dynamically
            const requiredFields = currentAssignment.required_fields || ['matricule'];
            const studentInfo = {};
            
            for (const field of requiredFields) {
                const value = await vscode.window.showInputBox({
                    prompt: `Enter your ${field}`,
                    placeHolder: field === 'matricule' ? 'e.g., 12345678' : `Your ${field}`,
                    ignoreFocusOut: true
                });
                
                if (!value) {
                    vscode.window.showErrorMessage('Submission cancelled - all fields are required');
                    return;
                }
                
                studentInfo[field] = value;
            }
            
            const events = db.prepare('SELECT * FROM events ORDER BY timestamp').all();
            const code = await getCodeFiles();
            
            const payload = JSON.stringify({
                student_info: studentInfo,
                assignment_id: currentAssignment.assignment_id,
                events: events,
                code: code
            });
            
            await makeRequest(currentAssignment.server + '/api/submit', payload);
            
            vscode.window.showInformationMessage('✅ Assignment submitted successfully!');
            db.close();
            db = null;
            statusBarItem.hide();
            
        } catch (error) {
            vscode.window.showErrorMessage(`Submission failed: ${error.message}`);
        }
    });
}

async function getCodeFiles() {
    const files = {};
    const workspaceFolder = vscode.workspace.workspaceFolders[0].uri.fsPath;
    const patterns = currentAssignment.track_patterns || ['*.py'];
    
    for (const pattern of patterns) {
        const filePattern = new vscode.RelativePattern(workspaceFolder, pattern);
        const uris = await vscode.workspace.findFiles(filePattern);
        
        for (const uri of uris) {
            const relativePath = path.relative(workspaceFolder, uri.fsPath);
            files[relativePath] = fs.readFileSync(uri.fsPath, 'utf8');
        }
    }
    
    return files;
}

function makeRequest(url, data) {
    return new Promise((resolve, reject) => {
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
                    reject(new Error(`HTTP ${res.statusCode}: ${body}`));
                }
            });
        });
        
        req.on('error', reject);
        req.write(data);
        req.end();
    });
}

function disableMonitoring(context) {
    if (currentAssignment) {
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
}

function deactivate() {
    if (db) {
        db.close();
    }
}

module.exports = {
    activate,
    deactivate
};
