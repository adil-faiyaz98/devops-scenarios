/**
 * Advanced structured logging for Pulumi deployments
 */

export enum LogLevel {
    DEBUG = 'DEBUG',
    INFO = 'INFO',
    WARN = 'WARN',
    ERROR = 'ERROR',
}

export interface LogEntry {
    timestamp: string;
    level: LogLevel;
    message: string;
    context: string;
    data?: any;
}

export class Logger {
    private context: string;
    private minLevel: LogLevel;

    constructor(context: string, minLevel: LogLevel = LogLevel.INFO) {
        this.context = context;
        this.minLevel = minLevel;
    }

    /**
     * Log a debug message
     * @param message The message to log
     * @param data Optional data to include in the log
     */
    debug(message: string, data?: any): void {
        this.log(LogLevel.DEBUG, message, data);
    }

    /**
     * Log an info message
     * @param message The message to log
     * @param data Optional data to include in the log
     */
    info(message: string, data?: any): void {
        this.log(LogLevel.INFO, message, data);
    }

    /**
     * Log a warning message
     * @param message The message to log
     * @param data Optional data to include in the log
     */
    warn(message: string, data?: any): void {
        this.log(LogLevel.WARN, message, data);
    }

    /**
     * Log an error message
     * @param message The message to log
     * @param data Optional data to include in the log
     */
    error(message: string, data?: any): void {
        this.log(LogLevel.ERROR, message, data);
    }

    /**
     * Log a message at the specified level
     * @param level The log level
     * @param message The message to log
     * @param data Optional data to include in the log
     */
    private log(level: LogLevel, message: string, data?: any): void {
        // Skip logging if the level is below the minimum level
        if (this.getLevelValue(level) < this.getLevelValue(this.minLevel)) {
            return;
        }

        const entry: LogEntry = {
            timestamp: new Date().toISOString(),
            level,
            message,
            context: this.context,
            data,
        };

        // In a real implementation, this would send logs to a centralized logging system
        // For now, we'll just log to the console
        const logString = `[${entry.timestamp}] [${entry.level}] [${entry.context}] ${entry.message}`;
        
        switch (level) {
            case LogLevel.DEBUG:
                console.debug(logString, data ? data : '');
                break;
            case LogLevel.INFO:
                console.info(logString, data ? data : '');
                break;
            case LogLevel.WARN:
                console.warn(logString, data ? data : '');
                break;
            case LogLevel.ERROR:
                console.error(logString, data ? data : '');
                break;
        }
    }

    /**
     * Get the numeric value of a log level for comparison
     * @param level The log level
     * @returns The numeric value
     */
    private getLevelValue(level: LogLevel): number {
        switch (level) {
            case LogLevel.DEBUG:
                return 0;
            case LogLevel.INFO:
                return 1;
            case LogLevel.WARN:
                return 2;
            case LogLevel.ERROR:
                return 3;
            default:
                return 1;
        }
    }

    /**
     * Set the minimum log level
     * @param level The minimum log level
     */
    setMinLevel(level: LogLevel): void {
        this.minLevel = level;
    }
}
