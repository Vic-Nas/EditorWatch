const vscode = require('vscode');

/**
 * Core tracking functionality - the actual keystroke logger
 * This is the simple, debuggable part
 */

class EventTracker {
    constructor() {
        this.events = [];
    }

    /**
     * Track a document change event
     */
    trackChange(event) {
        const change = event.contentChanges[0];
        if (!change) return;

        // Determine type and count
        let type, charCount;
        
        if (change.text && change.rangeLength > 0) {
            // REPLACEMENT (e.g., Copilot suggestion)
            // Use the NET change: new text length - old text length
            const netChange = change.text.length - change.rangeLength;
            if (netChange > 0) {
                type = 'insert';
                charCount = netChange;
            } else if (netChange < 0) {
                type = 'delete';
                charCount = Math.abs(netChange);
            } else {
                // Same length replacement, count as insert
                type = 'insert';
                charCount = change.text.length;
            }
        } else if (change.text) {
            // PURE INSERT
            type = 'insert';
            charCount = change.text.length;
        } else {
            // PURE DELETE
            type = 'delete';
            charCount = change.rangeLength || 0;
        }

        this.events.push({
            id: this.events.length + 1,
            timestamp: Date.now(),
            type: type,
            file: event.document.fileName,
            char_count: charCount
        });
    }

    /**
     * Track a save event
     */
    trackSave(fileName) {
        console.log(`[TRACKER] ${fileName} - save`);
        
        this.events.push({
            id: this.events.length + 1,
            timestamp: Date.now(),
            type: 'save',
            file: fileName,
            char_count: 0
        });
    }

    /**
     * Get all events
     */
    getEvents() {
        return this.events;
    }

    /**
     * Clear all events
     */
    clear() {
        this.events = [];
    }
}

module.exports = { EventTracker };