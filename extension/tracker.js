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
        // DEBUG: See what VSCode is sending us
        console.log(`[TRACKER DEBUG] contentChanges.length: ${event.contentChanges.length}`);
        
        const change = event.contentChanges[0];
        if (!change) return;

        const type = change.text ? 'insert' : 'delete';
        const charCount = Math.abs(change.text?.length || change.rangeLength || 0);

        // DEBUG: Log details
        console.log(`[TRACKER] ${event.document.fileName}`);
        console.log(`  Type: ${type}`);
        console.log(`  Char count: ${charCount}`);
        console.log(`  change.text.length: ${change.text?.length}`);
        console.log(`  change.rangeLength: ${change.rangeLength}`);
        
        // If there are multiple changes, we might be missing them!
        if (event.contentChanges.length > 1) {
            console.log(`  ⚠️  WARNING: ${event.contentChanges.length} changes, but only tracking first one!`);
            const total = event.contentChanges.reduce((sum, c) => sum + (c.text?.length || c.rangeLength || 0), 0);
            console.log(`  Total if we summed all changes: ${total}`);
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