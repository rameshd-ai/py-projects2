"""
Background thread execution and pytest runner.
Handles non-blocking test execution with real-time log streaming.
"""
import subprocess
import threading
import time
import os
import queue
from typing import Optional, Callable
from datetime import datetime
from flask_socketio import SocketIO

from .config_models import TestRunConfig
from .report_models import RunSummary, PillarResult


class BackgroundRunner:
    """Manages background execution of pytest with log streaming."""
    
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.current_run: Optional[dict] = None
        self.cancel_event = threading.Event()
    
    def start_run(self, run_id: str, config: TestRunConfig, log_callback: Optional[Callable] = None) -> threading.Thread:
        """
        Start a test run in a background thread.
        
        Args:
            run_id: Unique run identifier
            config: Test configuration
            log_callback: Optional callback for log messages
            
        Returns:
            Thread object running the tests
        """
        print(f"[DEBUG] start_run called with run_id={run_id}")
        
        if self.current_run is not None:
            print(f"[DEBUG] Run already in progress: {self.current_run}")
            raise RuntimeError("A test run is already in progress")
        
        print(f"[DEBUG] Initializing cancel event")
        # Initialize cancel event if not exists
        if not hasattr(self, 'cancel_event'):
            self.cancel_event = threading.Event()
        self.cancel_event.clear()
        
        print(f"[DEBUG] Defining run_tests function")
        
        def run_tests():
            """Execute pytest in background thread."""
            print(f"[DEBUG] ==================== INSIDE run_tests() ====================")
            print(f"[DEBUG] run_tests function executing for run_id: {run_id}")
            try:
                # CRITICAL: Emit log immediately to confirm thread started
                print(f"[DEBUG] About to emit initial log...")
                try:
                    self.socketio.emit('log', {
                        'level': 'info',
                        'message': f'[THREAD] Background thread started for run {run_id}'
                    }, )
                    print(f"[DEBUG] Successfully emitted initial log")
                except Exception as e:
                    print(f"[ERROR] Failed to emit initial log: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Update run state
                self.current_run = {
                    "run_id": run_id,
                    "status": "running",
                    "config": config,
                    "start_time": time.time()
                }
                
                # Emit start event (broadcast to all, and also to room)
                start_data = {
                    'run_id': run_id,
                    'timestamp': datetime.now().isoformat()
                }
                try:
                    self.socketio.emit('run_started', start_data, )
                    self.socketio.emit('run_started', start_data, room=f"run_{run_id}")
                    print(f"[DEBUG] Emitted run_started event for {run_id}")
                except Exception as e:
                    print(f"[ERROR] Failed to emit run_started: {e}")
                
                # Immediate log to confirm start
                try:
                    self.socketio.emit('log', {
                        'level': 'success',
                        'message': f'[STARTED] Test run {run_id} has begun execution'
                    }, )
                    print(f"[DEBUG] Emitted STARTED log")
                except Exception as e:
                    print(f"[ERROR] Failed to emit STARTED log: {e}")
                
                self.socketio.emit('log', {
                    'level': 'info',
                    'message': f'[CONFIG] Testing URL: {config.base_url}'
                }, )
                
                self.socketio.emit('log', {
                    'level': 'info',
                    'message': f'[CONFIG] Browsers: {", ".join(config.browsers)}'
                }, )
                
                self.socketio.emit('log', {
                    'level': 'info',
                    'message': f'[CONFIG] Devices: {", ".join(config.devices)}'
                }, )
                
                self.socketio.emit('log', {
                    'level': 'info',
                    'message': f'[CONFIG] Pillars: {", ".join(map(str, config.pillars))}'
                }, )
                
                # Build pytest command
                pytest_args = [
                    'pytest',
                    '-v',
                    '-s',  # Disable output capturing for real-time streaming
                    '--tb=short',
                    f'--run-id={run_id}',
                    f'--base-url={config.base_url}',
                ]
                
                # Add browser selection
                if config.browsers:
                    pytest_args.append(f'--browsers={",".join(config.browsers)}')
                
                # Add device selection
                if config.devices:
                    pytest_args.append(f'--devices={",".join(config.devices)}')
                
                # Add pillar selection
                if config.pillars:
                    pytest_args.append(f'--pillars={",".join(map(str, config.pillars))}')
                
                # Add sitemap URL if provided
                if config.sitemap_url:
                    pytest_args.append(f'--sitemap-url={config.sitemap_url}')
                
                # Select test files based on pillars
                test_files = []
                pillar_map = {
                    1: 'tests/test_ui_responsiveness.py',
                    2: 'tests/test_site_structure.py',
                    3: 'tests/test_user_flows.py',
                    4: 'tests/test_browser_health.py',
                    5: 'tests/test_compatibility.py',
                    6: 'tests/test_seo_metadata.py'
                }
                
                for pillar in config.pillars:
                    test_file = pillar_map.get(pillar)
                    if test_file and os.path.exists(test_file):
                        test_files.append(test_file)
                
                if not test_files:
                    # If no specific test files, run all tests
                    pytest_args.append('tests/')
                else:
                    pytest_args.extend(test_files)
                
                # Emit that pytest is starting
                self.socketio.emit('log', {
                    'level': 'info',
                    'message': f'[STEP 1/4] Building pytest command...'
                }, )
                
                self.socketio.emit('log', {
                    'level': 'info',
                    'message': f'[STEP 2/4] Pytest command: {" ".join(pytest_args)}'
                }, )
                
                # Check if pytest is available (try venv first, then system)
                try:
                    import shutil
                    import sys
                    
                    # Try to find pytest in venv first
                    venv_pytest = None
                    if os.path.exists('venv'):
                        if sys.platform == 'win32':
                            venv_pytest = os.path.join('venv', 'Scripts', 'pytest.exe')
                        else:
                            venv_pytest = os.path.join('venv', 'bin', 'pytest')
                        
                        if os.path.exists(venv_pytest):
                            pytest_path = venv_pytest
                            self.socketio.emit('log', {
                                'level': 'info',
                                'message': f'[STEP 3/4] Found pytest in venv: {pytest_path}'
                            }, )
                        else:
                            # Try system pytest
                            pytest_path = shutil.which('pytest')
                            if pytest_path:
                                self.socketio.emit('log', {
                                    'level': 'info',
                                    'message': f'[STEP 3/4] Found system pytest: {pytest_path}'
                                }, )
                            else:
                                raise Exception('pytest not found in venv or PATH')
                    else:
                        # No venv, try system
                        pytest_path = shutil.which('pytest')
                        if not pytest_path:
                            raise Exception('pytest not found in PATH and no venv detected')
                        self.socketio.emit('log', {
                            'level': 'info',
                            'message': f'[STEP 3/4] Found system pytest: {pytest_path}'
                        }, )
                    
                    # Use the found pytest path
                    if pytest_path and pytest_path != 'pytest':
                        pytest_args[0] = pytest_path
                        
                except Exception as e:
                    self.socketio.emit('log', {
                        'level': 'error',
                        'message': f'[ERROR] pytest not found: {e}. Make sure pytest is installed in venv.'
                    }, )
                    raise
                
                # Start pytest process
                self.socketio.emit('log', {
                    'level': 'info',
                    'message': f'[STEP 4/4] Starting pytest process...'
                }, )
                
                try:
                    import sys
                    # Use python -m pytest to ensure we use the right environment
                    if os.path.exists('venv'):
                        # On Windows, use venv python
                        if sys.platform == 'win32':
                            python_exe = os.path.join('venv', 'Scripts', 'python.exe')
                        else:
                            python_exe = os.path.join('venv', 'bin', 'python')
                        
                        if os.path.exists(python_exe):
                            # Replace 'pytest' with 'python -m pytest' using venv python
                            pytest_args = [python_exe, '-m', 'pytest'] + pytest_args[1:]
                            self.socketio.emit('log', {
                                'level': 'info',
                                'message': f'[INFO] Using venv Python: {python_exe}'
                            }, )
                        else:
                            self.socketio.emit('log', {
                                'level': 'warning',
                                'message': f'[WARNING] venv Python not found at {python_exe}, using system pytest'
                            }, )
                    
                    self.socketio.emit('log', {
                        'level': 'info',
                        'message': f'[INFO] Final command: {" ".join(pytest_args)}'
                    }, )
                    
                    # Set up environment with unbuffered output
                    env = os.environ.copy()
                    env['PYTHONUNBUFFERED'] = '1'  # Force unbuffered output
                    
                    process = subprocess.Popen(
                        pytest_args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,  # Line buffered for real-time output
                        universal_newlines=True,
                        cwd=os.getcwd(),  # Ensure we're in the right directory
                        env=env  # Pass environment variables with unbuffered flag
                    )
                    
                    # Emit that process started
                    self.socketio.emit('log', {
                        'level': 'success',
                        'message': f'[SUCCESS] Pytest process started (PID: {process.pid})'
                    }, )
                    
                    self.socketio.emit('log', {
                        'level': 'info',
                        'message': f'[INFO] Waiting for pytest output...'
                    }, )
                    
                except Exception as e:
                    self.socketio.emit('log', {
                        'level': 'error',
                        'message': f'[ERROR] Failed to start pytest: {str(e)}'
                    }, )
                    raise
                
                # Stream output in real-time using a separate thread for reading
                # This avoids blocking on Windows
                import queue
                output_queue = queue.Queue()
                line_count = 0
                last_progress_emit = time.time()
                last_line_time = time.time()
                
                def read_output():
                    """Read process output in a separate thread."""
                    try:
                        line_count = 0
                        for line in iter(process.stdout.readline, ''):
                            if line:
                                # Strip and put line in queue immediately
                                line_clean = line.rstrip()
                                if line_clean:  # Only queue non-empty lines
                                    output_queue.put(line_clean)
                                    line_count += 1
                                    # Emit immediate feedback every 10 lines
                                    if line_count % 10 == 0:
                                        self.socketio.emit('log', {
                                            'level': 'info',
                                            'message': f'[PROGRESS] Read {line_count} lines from pytest output...'
                                        }, )
                        output_queue.put(None)  # Signal end of output
                        self.socketio.emit('log', {
                            'level': 'info',
                            'message': f'[COMPLETE] Finished reading output ({line_count} total lines)'
                        }, )
                    except Exception as e:
                        error_msg = f'[ERROR] Error reading output: {e}'
                        output_queue.put(error_msg)
                        self.socketio.emit('log', {
                            'level': 'error',
                            'message': error_msg
                        }, )
                        output_queue.put(None)
                
                # Start output reader thread
                reader_thread = threading.Thread(target=read_output, daemon=True)
                reader_thread.start()
                
                self.socketio.emit('log', {
                    'level': 'info',
                    'message': '[INFO] Started output reader thread...'
                }, )
                
                self.socketio.emit('log', {
                    'level': 'info',
                    'message': '[INFO] Waiting for pytest output (this may take a few seconds)...'
                }, )
                
                # Read from queue (non-blocking)
                while True:
                    if self.cancel_event.is_set():
                        process.terminate()
                        self.socketio.emit('log', {
                            'level': 'warning',
                            'message': 'Test run cancelled by user'
                        }, )
                        break
                    
                    # Check if process has ended
                    return_code = process.poll()
                    if return_code is not None:
                        # Process ended, read any remaining output from queue
                        try:
                            while True:
                                try:
                                    line = output_queue.get_nowait()
                                    if line is None:
                                        break
                                    if line.strip():
                                        line_count += 1
                                        log_level = self._parse_log_level(line.rstrip())
                                        self.socketio.emit('log', {
                                            'level': log_level,
                                            'message': line.rstrip()
                                        }, )
                                except queue.Empty:
                                    break
                        except Exception:
                            pass
                        break
                    
                    # Try to get a line from queue (non-blocking)
                    try:
                        line = output_queue.get(timeout=0.1)
                        if line is None:
                            # End of output signal
                            break
                        
                        if line:
                            line_count += 1
                            line_stripped = str(line).strip() if line else ''
                            if line_stripped:  # Only process non-empty lines
                                last_line_time = time.time()
                                
                                # Emit log line (broadcast to all and to room)
                                log_level = self._parse_log_level(line_stripped)
                                log_data = {
                                    'level': log_level,
                                    'message': line_stripped
                                }
                                self.socketio.emit('log', log_data, )
                                self.socketio.emit('log', log_data, room=f"run_{run_id}")
                                
                                if log_callback:
                                    log_callback(line_stripped)
                    except queue.Empty:
                        # No line available, check for timeouts
                        current_time = time.time()
                        
                        # Emit progress updates every 5 seconds
                        if current_time - last_progress_emit >= 5:
                            elapsed = current_time - self.current_run["start_time"]
                            self.socketio.emit('log', {
                                'level': 'info',
                                'message': f'[PROGRESS] Still running... ({int(elapsed)}s elapsed, {line_count} log lines, PID: {process.pid})'
                            }, )
                            last_progress_emit = current_time
                        
                        # Check for no output timeout
                        time_since_last_line = current_time - last_line_time
                        if line_count == 0 and time_since_last_line > 15:
                            # First warning at 15 seconds
                            self.socketio.emit('log', {
                                'level': 'warning',
                                'message': f'[WARNING] No output from pytest for {int(time_since_last_line)}s. Playwright may be installing/starting browsers (this can take 30-60s on first run)...'
                            }, )
                            if process.poll() is None:
                                self.socketio.emit('log', {
                                    'level': 'info',
                                    'message': f'[INFO] Process is still running (PID: {process.pid}). This is normal - Playwright browser initialization can take time.'
                                }, )
                        elif line_count == 0 and time_since_last_line > 30:
                            # Second warning at 30 seconds
                            self.socketio.emit('log', {
                                'level': 'warning',
                                'message': f'[WARNING] Still no output after {int(time_since_last_line)}s. Check server terminal for errors.'
                            }, )
                
                # Wait for process to complete
                process.wait()
                
                # Update status
                if self.cancel_event.is_set():
                    status = "cancelled"
                elif process.returncode == 0:
                    status = "completed"
                else:
                    status = "failed"
                
                self.current_run["status"] = status
                self.current_run["duration"] = time.time() - self.current_run["start_time"]
                
                # Emit completion event (broadcast to all and to room)
                completion_data = {
                    'run_id': run_id,
                    'status': status,
                    'duration': self.current_run["duration"],
                    'timestamp': datetime.now().isoformat()
                }
                self.socketio.emit('run_completed', completion_data, )
                self.socketio.emit('run_completed', completion_data, room=f"run_{run_id}")
                
            except Exception as e:
                # Handle errors
                error_data = {
                    'level': 'error',
                    'message': f'Fatal error: {str(e)}'
                }
                self.socketio.emit('log', error_data, )
                self.socketio.emit('log', error_data, room=f"run_{run_id}")
                
                if self.current_run:
                    self.current_run["status"] = "failed"
                
                completion_data = {
                    'run_id': run_id,
                    'status': 'failed',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                self.socketio.emit('run_completed', completion_data, )
                self.socketio.emit('run_completed', completion_data, room=f"run_{run_id}")
            
            finally:
                # Cleanup
                self.current_run = None
        
        # Start thread
        print(f"[DEBUG] Creating thread for run_tests")
        thread = threading.Thread(target=run_tests, daemon=True, name=f"TestRun-{run_id}")
        print(f"[DEBUG] Starting thread: {thread.name}")
        thread.start()
        print(f"[DEBUG] Thread started, is_alive={thread.is_alive()}")
        
        return thread
    
    def cancel_run(self):
        """Cancel the current test run."""
        if self.current_run is None:
            return False
        
        self.cancel_event.set()
        return True
    
    def get_current_run(self) -> Optional[dict]:
        """Get current run status."""
        return self.current_run
    
    def is_running(self) -> bool:
        """Check if a run is currently in progress."""
        return self.current_run is not None and self.current_run["status"] == "running"
    
    @staticmethod
    def _parse_log_level(line: str) -> str:
        """Parse log level from pytest output."""
        line_lower = line.lower()
        if 'error' in line_lower or 'failed' in line_lower or 'traceback' in line_lower:
            return 'error'
        elif 'warning' in line_lower or 'warn' in line_lower:
            return 'warning'
        elif 'passed' in line_lower or 'success' in line_lower:
            return 'success'
        else:
            return 'info'
