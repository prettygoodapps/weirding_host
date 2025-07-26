#!/usr/bin/env python3
"""
Logging Module for Weirding Host Utility

This module provides comprehensive logging capabilities for the Weirding Module
setup process, including structured logging, progress tracking, and error reporting.
"""

import logging
import json
import time
import os
import sys
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum


class LogLevel(Enum):
    """Log levels for Weirding operations."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Categories for different types of operations."""
    SYSTEM = "system"
    PARTITIONING = "partitioning"
    BOOTLOADER = "bootloader"
    OS_INSTALL = "os_install"
    AI_STACK = "ai_stack"
    HARDWARE = "hardware"
    USER_ACTION = "user_action"
    RECOVERY = "recovery"


@dataclass
class LogEntry:
    """Structured log entry for Weirding operations."""
    timestamp: str
    level: str
    category: str
    operation: str
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    success: Optional[bool] = None
    error_code: Optional[str] = None


class WeirdingLogger:
    """Comprehensive logging system for Weirding Module setup."""
    
    def __init__(self, log_dir: Optional[Path] = None, session_id: Optional[str] = None):
        """
        Initialize the Weirding logger.
        
        Args:
            log_dir: Directory for log files (default: ~/.weirding_logs)
            session_id: Unique session identifier (default: timestamp-based)
        """
        self.log_dir = log_dir or Path.home() / ".weirding_logs"
        self.log_dir.mkdir(exist_ok=True)
        
        self.session_id = session_id or f"weirding_{int(time.time())}"
        self.session_start = time.time()
        
        # Create session-specific log files
        self.main_log_file = self.log_dir / f"{self.session_id}.log"
        self.json_log_file = self.log_dir / f"{self.session_id}.json"
        self.error_log_file = self.log_dir / f"{self.session_id}_errors.log"
        
        # Initialize loggers
        self._setup_loggers()
        
        # Session tracking
        self.operations: List[LogEntry] = []
        self.current_operation: Optional[str] = None
        self.operation_start_time: Optional[float] = None
        
        # Log session start
        self.log_info(LogCategory.SYSTEM, "session_start", 
                     f"Weirding Module setup session started: {self.session_id}")
    
    def _setup_loggers(self):
        """Set up Python logging infrastructure."""
        # Main logger
        self.main_logger = logging.getLogger(f"weirding.{self.session_id}")
        self.main_logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        self.main_logger.handlers.clear()
        
        # File handler for main log
        main_handler = logging.FileHandler(self.main_log_file)
        main_handler.setLevel(logging.DEBUG)
        main_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        main_handler.setFormatter(main_formatter)
        self.main_logger.addHandler(main_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        self.main_logger.addHandler(console_handler)
        
        # Error logger
        self.error_logger = logging.getLogger(f"weirding.{self.session_id}.errors")
        self.error_logger.setLevel(logging.WARNING)
        
        error_handler = logging.FileHandler(self.error_log_file)
        error_handler.setLevel(logging.WARNING)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n'
        )
        error_handler.setFormatter(error_formatter)
        self.error_logger.addHandler(error_handler)
    
    def start_operation(self, category: LogCategory, operation: str, message: str, 
                       details: Optional[Dict[str, Any]] = None):
        """
        Start tracking a new operation.
        
        Args:
            category: Operation category
            operation: Operation name
            message: Description of the operation
            details: Additional operation details
        """
        self.current_operation = operation
        self.operation_start_time = time.time()
        
        self.log_info(category, operation, f"Started: {message}", details)
    
    def end_operation(self, success: bool, message: str = None, 
                     error_code: str = None, details: Optional[Dict[str, Any]] = None):
        """
        End the current operation and log results.
        
        Args:
            success: Whether the operation succeeded
            message: Final message for the operation
            error_code: Error code if operation failed
            details: Additional details about the operation result
        """
        if not self.current_operation or not self.operation_start_time:
            self.log_warning(LogCategory.SYSTEM, "logging_error", 
                           "end_operation called without active operation")
            return
        
        duration_ms = int((time.time() - self.operation_start_time) * 1000)
        
        level = LogLevel.INFO if success else LogLevel.ERROR
        final_message = message or f"{'Completed' if success else 'Failed'}: {self.current_operation}"
        
        self._log_entry(level, LogCategory.SYSTEM, self.current_operation, 
                       final_message, details, duration_ms, success, error_code)
        
        self.current_operation = None
        self.operation_start_time = None
    
    def log_debug(self, category: LogCategory, operation: str, message: str, 
                  details: Optional[Dict[str, Any]] = None):
        """Log debug message."""
        self._log_entry(LogLevel.DEBUG, category, operation, message, details)
    
    def log_info(self, category: LogCategory, operation: str, message: str, 
                 details: Optional[Dict[str, Any]] = None):
        """Log info message."""
        self._log_entry(LogLevel.INFO, category, operation, message, details)
    
    def log_warning(self, category: LogCategory, operation: str, message: str, 
                   details: Optional[Dict[str, Any]] = None):
        """Log warning message."""
        self._log_entry(LogLevel.WARNING, category, operation, message, details)
    
    def log_error(self, category: LogCategory, operation: str, message: str, 
                  details: Optional[Dict[str, Any]] = None, error_code: str = None):
        """Log error message."""
        self._log_entry(LogLevel.ERROR, category, operation, message, details, 
                       error_code=error_code)
    
    def log_critical(self, category: LogCategory, operation: str, message: str, 
                    details: Optional[Dict[str, Any]] = None, error_code: str = None):
        """Log critical message."""
        self._log_entry(LogLevel.CRITICAL, category, operation, message, details, 
                       error_code=error_code)
    
    def _log_entry(self, level: LogLevel, category: LogCategory, operation: str, 
                   message: str, details: Optional[Dict[str, Any]] = None,
                   duration_ms: Optional[int] = None, success: Optional[bool] = None,
                   error_code: Optional[str] = None):
        """Create and store a log entry."""
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level.value,
            category=category.value,
            operation=operation,
            message=message,
            details=details,
            duration_ms=duration_ms,
            success=success,
            error_code=error_code
        )
        
        self.operations.append(entry)
        
        # Log to Python logger
        log_message = f"[{category.value}:{operation}] {message}"
        if details:
            log_message += f" | Details: {json.dumps(details, default=str)}"
        
        if level == LogLevel.DEBUG:
            self.main_logger.debug(log_message)
        elif level == LogLevel.INFO:
            self.main_logger.info(log_message)
        elif level == LogLevel.WARNING:
            self.main_logger.warning(log_message)
            self.error_logger.warning(log_message)
        elif level == LogLevel.ERROR:
            self.main_logger.error(log_message)
            self.error_logger.error(log_message)
        elif level == LogLevel.CRITICAL:
            self.main_logger.critical(log_message)
            self.error_logger.critical(log_message)
        
        # Write to JSON log
        self._write_json_entry(entry)
    
    def _write_json_entry(self, entry: LogEntry):
        """Write log entry to JSON file."""
        try:
            with open(self.json_log_file, 'a') as f:
                json.dump(asdict(entry), f, default=str)
                f.write('\n')
        except Exception as e:
            self.main_logger.error(f"Failed to write JSON log entry: {e}")
    
    def log_system_info(self, system_info: Dict[str, Any]):
        """Log system information."""
        self.log_info(LogCategory.SYSTEM, "system_info", "System information collected", 
                     system_info)
    
    def log_drive_info(self, drive_info: Dict[str, Any]):
        """Log drive information."""
        self.log_info(LogCategory.SYSTEM, "drive_info", "Drive information collected", 
                     drive_info)
    
    def log_partition_plan(self, plan_info: Dict[str, Any]):
        """Log partition plan details."""
        self.log_info(LogCategory.PARTITIONING, "partition_plan", 
                     "Partition plan created", plan_info)
    
    def log_command_execution(self, command: List[str], return_code: int, 
                            stdout: str = None, stderr: str = None):
        """Log command execution details."""
        details = {
            "command": command,
            "return_code": return_code,
            "stdout": stdout[:1000] if stdout else None,  # Limit output size
            "stderr": stderr[:1000] if stderr else None
        }
        
        if return_code == 0:
            self.log_debug(LogCategory.SYSTEM, "command_exec", 
                          f"Command executed successfully: {' '.join(command)}", details)
        else:
            self.log_error(LogCategory.SYSTEM, "command_exec", 
                          f"Command failed: {' '.join(command)}", details, 
                          error_code=f"EXIT_{return_code}")
    
    def log_progress_update(self, operation: str, progress_percent: float, 
                           message: str = None):
        """Log progress update for long-running operations."""
        details = {"progress_percent": progress_percent}
        if message:
            details["progress_message"] = message
        
        self.log_debug(LogCategory.SYSTEM, operation, 
                      f"Progress: {progress_percent:.1f}%", details)
    
    def create_session_summary(self) -> Dict[str, Any]:
        """Create a summary of the current session."""
        session_duration = time.time() - self.session_start
        
        # Count operations by category and status
        category_counts = {}
        success_counts = {"success": 0, "failure": 0, "unknown": 0}
        error_codes = {}
        
        for entry in self.operations:
            # Count by category
            category = entry.category
            if category not in category_counts:
                category_counts[category] = 0
            category_counts[category] += 1
            
            # Count by success status
            if entry.success is True:
                success_counts["success"] += 1
            elif entry.success is False:
                success_counts["failure"] += 1
            else:
                success_counts["unknown"] += 1
            
            # Count error codes
            if entry.error_code:
                if entry.error_code not in error_codes:
                    error_codes[entry.error_code] = 0
                error_codes[entry.error_code] += 1
        
        return {
            "session_id": self.session_id,
            "start_time": datetime.fromtimestamp(self.session_start).isoformat(),
            "duration_seconds": int(session_duration),
            "total_operations": len(self.operations),
            "category_counts": category_counts,
            "success_counts": success_counts,
            "error_codes": error_codes,
            "log_files": {
                "main_log": str(self.main_log_file),
                "json_log": str(self.json_log_file),
                "error_log": str(self.error_log_file)
            }
        }
    
    def finalize_session(self, success: bool = True, final_message: str = None):
        """Finalize the logging session."""
        session_duration = time.time() - self.session_start
        
        summary = self.create_session_summary()
        
        final_msg = final_message or f"Session {'completed successfully' if success else 'ended with errors'}"
        
        self.log_info(LogCategory.SYSTEM, "session_end", final_msg, {
            "session_summary": summary,
            "total_duration_seconds": int(session_duration)
        })
        
        # Write session summary to separate file
        summary_file = self.log_dir / f"{self.session_id}_summary.json"
        try:
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
        except Exception as e:
            self.main_logger.error(f"Failed to write session summary: {e}")
    
    def get_recent_errors(self, limit: int = 10) -> List[LogEntry]:
        """Get recent error entries."""
        errors = [entry for entry in self.operations 
                 if entry.level in [LogLevel.ERROR.value, LogLevel.CRITICAL.value]]
        return errors[-limit:]
    
    def export_logs(self, export_path: Path, include_json: bool = True) -> bool:
        """
        Export logs to a specified directory.
        
        Args:
            export_path: Directory to export logs to
            include_json: Whether to include JSON logs
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            export_path.mkdir(parents=True, exist_ok=True)
            
            # Copy main log
            import shutil
            shutil.copy2(self.main_log_file, export_path / f"{self.session_id}.log")
            
            # Copy error log if it exists
            if self.error_log_file.exists():
                shutil.copy2(self.error_log_file, export_path / f"{self.session_id}_errors.log")
            
            # Copy JSON log if requested
            if include_json and self.json_log_file.exists():
                shutil.copy2(self.json_log_file, export_path / f"{self.session_id}.json")
            
            # Create summary
            summary = self.create_session_summary()
            with open(export_path / f"{self.session_id}_summary.json", 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            self.log_info(LogCategory.SYSTEM, "log_export", 
                         f"Logs exported to {export_path}")
            return True
            
        except Exception as e:
            self.log_error(LogCategory.SYSTEM, "log_export", 
                          f"Failed to export logs: {e}")
            return False


def create_progress_callback(logger: WeirdingLogger, category: LogCategory, 
                           operation: str) -> callable:
    """
    Create a progress callback function for use with installation modules.
    
    Args:
        logger: WeirdingLogger instance
        category: Log category for progress updates
        operation: Operation name
        
    Returns:
        Callback function that logs progress updates
    """
    def progress_callback(message: str, progress: float = None):
        if progress is not None:
            logger.log_progress_update(operation, progress, message)
        else:
            logger.log_debug(category, operation, message)
    
    return progress_callback


def main():
    """Test the logging system."""
    logger = WeirdingLogger()
    
    # Test basic logging
    logger.log_info(LogCategory.SYSTEM, "test", "Testing logging system")
    
    # Test operation tracking
    logger.start_operation(LogCategory.PARTITIONING, "test_partition", 
                          "Testing partition operation")
    
    time.sleep(1)  # Simulate work
    
    logger.log_progress_update("test_partition", 50.0, "Halfway done")
    
    time.sleep(1)  # Simulate more work
    
    logger.end_operation(True, "Partition test completed successfully")
    
    # Test error logging
    logger.log_error(LogCategory.SYSTEM, "test_error", "This is a test error", 
                     {"error_details": "Test error details"}, "TEST_ERROR_001")
    
    # Create summary
    summary = logger.create_session_summary()
    print("\nSession Summary:")
    print(json.dumps(summary, indent=2, default=str))
    
    # Finalize session
    logger.finalize_session(True, "Test session completed")


if __name__ == "__main__":
    main()