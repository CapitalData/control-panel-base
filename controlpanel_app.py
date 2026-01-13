"""
Control Panel - Application Manager
====================================
Manage Python tools and Dash apps from a single interface.

Technical Notes:
----------------
- Dash apps are spawned as subprocesses with modified environment variables:
  - WERKZEUG_RUN_MAIN='true' - Disables Flask's reloader in child processes
  - WERKZEUG_SERVER_FD removed - Prevents socket inheritance conflicts
  - close_fds=True and start_new_session=True - Full process isolation

- Each managed app must handle WERKZEUG_RUN_MAIN='true' to disable hot-reload:
    use_reloader = os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
    app.run_server(..., use_reloader=use_reloader)

- This control panel runs on port 8060
- Status updates every 2 seconds via dcc.Interval

Usage:
------
1. Toggle switch to start/stop applications
2. Output console shows stdout/stderr from each process
3. "Open" link available when Dash apps are running

Military Console Theme:
-----------------------
Styled as a retro tank/industrial control panel with:
- Brushed metal textures
- Corner screws (Phillips head)
- Industrial warning labels
- Gauge-style indicator panels
- Heavy-duty toggle switches
"""
import os
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import json
import psutil
import yaml

import dash
import dash_bootstrap_components as dbc
from dash import (ALL, MATCH, ClientsideFunction, Input, Output, State, callback,
                  clientside_callback, ctx, dcc, html, no_update)

# Initialize the app with dark military theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
)

# Inject custom CSS via index_string
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Control Station</title>
        {%favicon%}
        {%css%}
        <style>
        /* Base metal panel styling */
        .military-panel {
            background: linear-gradient(145deg, #3a3a3a 0%, #2a2a2a 50%, #1a1a1a 100%);
            border: 4px solid #555;
            border-radius: 8px;
            box-shadow: 
                inset 0 2px 4px rgba(255,255,255,0.1),
                inset 0 -2px 4px rgba(0,0,0,0.3),
                0 8px 16px rgba(0,0,0,0.5);
            position: relative;
        }

        /* Corner screws */
        .screw {
            width: 16px;
            height: 16px;
            background: radial-gradient(circle at 30% 30%, #888 0%, #444 50%, #222 100%);
            border-radius: 50%;
            position: absolute;
            box-shadow: 
                inset 0 1px 2px rgba(255,255,255,0.3),
                0 2px 4px rgba(0,0,0,0.5);
        }
        .screw::before {
            content: "+";
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #222;
            font-weight: bold;
            font-size: 10px;
        }
        .screw-tl { top: 8px; left: 8px; }
        .screw-tr { top: 8px; right: 8px; }
        .screw-bl { bottom: 8px; left: 8px; }
        .screw-br { bottom: 8px; right: 8px; }

        /* Gauge panel for app cards */
        .gauge-panel {
            background: linear-gradient(180deg, #2d2d2d 0%, #1a1a1a 100%);
            border: 3px solid #444;
            border-radius: 6px;
            box-shadow:
                inset 0 4px 8px rgba(0,0,0,0.4),
                inset 0 -2px 4px rgba(255,255,255,0.05);
            position: relative;
            padding: 20px;
            margin: 10px 0;
        }

        /* Indicator light housing */
        .indicator-housing {
            background: #111;
            border: 2px solid #333;
            border-radius: 50%;
            padding: 4px;
            display: inline-block;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.8);
        }

        /* Toggle switch base */
        .toggle-base {
            background: linear-gradient(180deg, #3a3a3a, #222);
            border: 2px solid #555;
            border-radius: 4px;
            padding: 8px 12px;
            display: inline-block;
        }

        /* Emergency kill button */
        .kill-button {
            background: linear-gradient(180deg, #8b1e1e, #4a0f0f);
            border: 2px solid #ff3b30;
            box-shadow: 0 0 12px rgba(255,59,48,0.4), inset 0 2px 4px rgba(0,0,0,0.4);
            color: #ffdedb;
            font-family: 'Courier New', monospace;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .kill-button:disabled {
            opacity: 0.4;
            box-shadow: none;
            border-color: #555;
        }

        /* Radio-style purge switch */
        .kill-radio {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            padding: 6px 12px;
            background: linear-gradient(180deg, #5a0f0f, #2b0505);
            border: 2px solid #ff3b30;
            border-radius: 20px;
            box-shadow: 0 0 12px rgba(255,59,48,0.35), inset 0 2px 4px rgba(0,0,0,0.6);
        }
        .kill-radio .form-check {
            margin: 0;
            padding: 0;
        }
        .kill-radio .form-check:first-child {
            display: none;
        }
        .kill-radio .form-check-input {
            width: 18px;
            height: 18px;
            cursor: pointer;
            border: 2px solid #ff3b30;
            background-color: transparent;
        }
        .kill-radio .form-check-input:checked {
            background-color: #ff3b30;
            box-shadow: 0 0 10px rgba(255,59,48,0.8);
        }
        .kill-radio .form-check-label {
            font-family: 'Courier New', monospace;
            font-size: 11px;
            color: #ffbeb4;
            letter-spacing: 2px;
            cursor: pointer;
            text-transform: uppercase;
        }

        /* Label plate styling */
        .label-plate {
            background: linear-gradient(180deg, #c4a747 0%, #8b7a35 100%);
            color: #1a1a1a;
            font-family: 'Courier New', monospace;
            font-weight: bold;
            font-size: 12px;
            padding: 4px 12px;
            border-radius: 3px;
            border: 1px solid #6b5a25;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }

        /* Steel blue divider bar */
        .warning-stripe {
            background: linear-gradient(180deg, #5a7c9a 0%, #4a6c8a 50%, #3a5c7a 100%);
            height: 8px;
            border-radius: 2px;
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.4);
        }

        /* Output terminal styling */
        .terminal-output {
            background: #0a0a0a !important;
            color: #00ff00 !important;
            border: 3px solid #333 !important;
            font-family: 'Courier New', monospace !important;
            text-shadow: 0 0 5px rgba(0,255,0,0.5);
            box-shadow: inset 0 4px 12px rgba(0,0,0,0.8);
        }

        /* Knob styling */
        .control-knob {
            width: 40px;
            height: 40px;
            background: radial-gradient(circle at 35% 35%, #666 0%, #333 50%, #111 100%);
            border-radius: 50%;
            border: 2px solid #444;
            display: inline-block;
            position: relative;
            box-shadow:
                0 4px 8px rgba(0,0,0,0.5),
                inset 0 2px 4px rgba(255,255,255,0.1);
        }
        .control-knob::after {
            content: "";
            position: absolute;
            top: 8px;
            left: 50%;
            width: 3px;
            height: 12px;
            background: #ddd;
            transform: translateX(-50%);
            border-radius: 2px;
        }

        /* Rivet styling */
        .rivet {
            width: 8px;
            height: 8px;
            background: radial-gradient(circle at 30% 30%, #777, #333);
            border-radius: 50%;
            display: inline-block;
            margin: 0 4px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.5);
        }

        /* Header styling */
        .console-header {
            background: linear-gradient(180deg, #444 0%, #222 100%);
            border-bottom: 4px solid #111;
            padding: 20px;
            margin: -15px -15px 20px -15px;
            text-align: center;
        }

        .console-title {
            font-family: 'Courier New', monospace;
            font-weight: bold;
            letter-spacing: 4px;
            text-transform: uppercase;
            color: #d4a017;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }

        /* Status text styling */
        .status-text {
            font-family: 'Courier New', monospace;
            font-size: 11px;
            color: #888;
            text-transform: uppercase;
        }

        /* Animated running indicator */
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 0 5px 2px rgba(0,255,0,0.3); }
            50% { box-shadow: 0 0 15px 4px rgba(0,255,0,0.6); }
        }
        .indicator-running {
            animation: pulse-glow 1.5s ease-in-out infinite;
        }

        /* Persona scaffolding */
        .persona-wrapper {
            min-height: 100vh;
            transition: background 0.6s ease;
        }
        .persona-wrapper.persona-admin {
            background: radial-gradient(circle at 20% 0%, #2f2f2f 0%, #0c0c0c 60%);
        }
        .persona-wrapper.persona-developer {
            background: radial-gradient(circle at 15% 15%, #0c2038 0%, #030a12 65%);
        }
        .persona-wrapper.persona-public_user {
            background: radial-gradient(circle at 20% 10%, #2a3540 0%, #0f1519 65%);
        }
        .persona-wrapper.persona-scientist {
            background: radial-gradient(circle at 15% 15%, #0c2038 0%, #030a12 65%);
        }

        .persona-row {
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            padding: 12px 16px;
        }

        .persona-chip {
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            padding: 6px 16px;
            display: inline-flex;
            align-items: baseline;
            gap: 8px;
            background: rgba(0, 0, 0, 0.35);
        }
        .persona-chip__name {
            font-weight: 700;
            color: #f6d479;
            letter-spacing: 1px;
        }
        .persona-chip__desc {
            color: #aaa;
            font-size: 12px;
        }

        .persona-selector {
            min-width: 220px;
        }
        .persona-select-control {
            background-color: #111 !important;
            color: #f5f5f5 !important;
            border: 1px solid #555 !important;
            font-family: 'Courier New', monospace;
        }
        .persona-select-control:disabled {
            opacity: 0.35;
            cursor: not-allowed;
        }

        .persona-empty-alert {
            background: rgba(0,0,0,0.35) !important;
            border: 1px dashed rgba(255,255,255,0.25) !important;
            color: #ccc !important;
            text-align: center;
        }

        /* Scientist theme overrides */
        .persona-wrapper.persona-scientist .military-panel {
            background: linear-gradient(150deg, #0e223f 0%, #1b3552 45%, #050b14 100%);
            border-color: #5a8bbf;
            box-shadow:
                inset 0 2px 6px rgba(255,255,255,0.08),
                inset 0 -3px 8px rgba(0,0,0,0.65),
                0 10px 28px rgba(5,15,30,0.8);
        }
        .persona-wrapper.persona-scientist .console-title {
            color: #a4d7ff;
            text-shadow: 0 3px 6px rgba(0,0,0,0.7);
        }
        .persona-wrapper.persona-scientist .warning-stripe {
            background: linear-gradient(90deg, #c2d8f2, #6f93bf, #c2d8f2);
            box-shadow: inset 0 1px 3px rgba(10,30,55,0.6);
        }
        .persona-wrapper.persona-scientist .label-plate {
            background: linear-gradient(180deg, #eff4fa 0%, #9fb7ce 100%);
            color: #0d1f33;
            border-color: #6e8faa;
            box-shadow: 0 2px 6px rgba(12,25,45,0.6);
        }
        .persona-wrapper.persona-scientist .indicator-housing {
            background: #061120;
            border-color: #2c405c;
        }
        .persona-wrapper.persona-scientist .toggle-base {
            background: linear-gradient(180deg, #1e3a5c, #0f1f33);
            border-color: #55779c;
        }
        .persona-wrapper.persona-scientist .kill-button {
            background: linear-gradient(180deg, #b82f3b, #5d131a);
            border-color: #ff7b88;
            box-shadow: 0 0 18px rgba(255,123,136,0.35), inset 0 2px 4px rgba(0,0,0,0.4);
        }
        .persona-wrapper.persona-scientist .terminal-output {
            background: #010910 !important;
            color: #7ff9ff !important;
            border-color: #143246 !important;
            text-shadow: 0 0 7px rgba(127,249,255,0.35);
        }
        .persona-wrapper.persona-scientist .persona-row {
            background: rgba(10, 34, 60, 0.7);
            border-color: rgba(159, 201, 255, 0.2);
        }
        .persona-wrapper.persona-scientist .persona-chip {
            background: rgba(13, 38, 66, 0.8);
            border-color: #4f7ea9;
        }
        .persona-wrapper.persona-scientist .persona-chip__name {
            color: #9fd8ff;
        }
        .persona-wrapper.persona-scientist .persona-chip__desc {
            color: #8ab5d6;
        }
        .persona-wrapper.persona-scientist .screw {
            background: radial-gradient(circle at 30% 30%, #5a8bbf 0%, #2c4a6f 50%, #0d1f33 100%);
        }
        .persona-wrapper.persona-scientist .screw::before {
            color: #0d1f33;
        }

        /* Developer theme overrides (dark blue) */
        .persona-wrapper.persona-developer .military-panel {
            background: linear-gradient(150deg, #0e223f 0%, #1b3552 45%, #050b14 100%);
            border-color: #5a8bbf;
            box-shadow:
                inset 0 2px 6px rgba(255,255,255,0.08),
                inset 0 -3px 8px rgba(0,0,0,0.65),
                0 10px 28px rgba(5,15,30,0.8);
        }
        .persona-wrapper.persona-developer .console-title {
            color: #a4d7ff;
            text-shadow: 0 3px 6px rgba(0,0,0,0.7);
        }
        .persona-wrapper.persona-developer .warning-stripe {
            background: linear-gradient(90deg, #c2d8f2, #6f93bf, #c2d8f2);
            box-shadow: inset 0 1px 3px rgba(10,30,55,0.6);
        }
        .persona-wrapper.persona-developer .label-plate {
            background: linear-gradient(180deg, #eff4fa 0%, #9fb7ce 100%);
            color: #0d1f33;
            border-color: #6e8faa;
            box-shadow: 0 2px 6px rgba(12,25,45,0.6);
        }
        .persona-wrapper.persona-developer .indicator-housing {
            background: #061120;
            border-color: #2c405c;
        }
        .persona-wrapper.persona-developer .toggle-base {
            background: linear-gradient(180deg, #1e3a5c, #0f1f33);
            border-color: #55779c;
        }
        .persona-wrapper.persona-developer .kill-button {
            background: linear-gradient(180deg, #b82f3b, #5d131a);
            border-color: #ff7b88;
            box-shadow: 0 0 18px rgba(255,123,136,0.35), inset 0 2px 4px rgba(0,0,0,0.4);
        }
        .persona-wrapper.persona-developer .terminal-output {
            background: #010910 !important;
            color: #7ff9ff !important;
            border-color: #143246 !important;
            text-shadow: 0 0 7px rgba(127,249,255,0.35);
        }
        .persona-wrapper.persona-developer .persona-row {
            background: rgba(10, 34, 60, 0.7);
            border-color: rgba(159, 201, 255, 0.2);
        }
        .persona-wrapper.persona-developer .persona-chip {
            background: rgba(13, 38, 66, 0.8);
            border-color: #4f7ea9;
        }
        .persona-wrapper.persona-developer .persona-chip__name {
            color: #9fd8ff;
        }
        .persona-wrapper.persona-developer .persona-chip__desc {
            color: #8ab5d6;
        }
        .persona-wrapper.persona-developer .screw {
            background: radial-gradient(circle at 30% 30%, #5a8bbf 0%, #2c4a6f 50%, #0d1f33 100%);
        }
        .persona-wrapper.persona-developer .screw::before {
            color: #0d1f33;
        }

        /* Public User theme overrides (titanium/silver) */
        .persona-wrapper.persona-public_user .military-panel {
            background: linear-gradient(145deg, #c8d0d8 0%, #dfe3e8 50%, #c8d0d8 100%);
            border-color: #9ea7b0;
            box-shadow:
                inset 0 2px 4px rgba(255,255,255,0.6),
                inset 0 -2px 4px rgba(0,0,0,0.2),
                0 8px 16px rgba(0,0,0,0.3);
        }
        .persona-wrapper.persona-public_user .console-title {
            color: #4a5a6a;
            text-shadow: 0 1px 2px rgba(255,255,255,0.5);
        }
        .persona-wrapper.persona-public_user .warning-stripe {
            background: linear-gradient(180deg, #8b9dc3 0%, #7a8a9e 50%, #8b9dc3 100%);
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.3);
        }
        .persona-wrapper.persona-public_user .label-plate {
            background: linear-gradient(180deg, #f0f3f7 0%, #d5dce4 100%);
            color: #2c3e50;
            border-color: #a3b0c0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .persona-wrapper.persona-public_user .indicator-housing {
            background: #e8ecf0;
            border-color: #b0bec5;
        }
        .persona-wrapper.persona-public_user .toggle-base {
            background: linear-gradient(180deg, #dfe3e8, #c8d0d8);
            border-color: #9ea7b0;
        }
        .persona-wrapper.persona-public_user .kill-button {
            background: linear-gradient(180deg, #c44a4a, #9a3232);
            border-color: #d55555;
            box-shadow: 0 0 12px rgba(213,85,85,0.3), inset 0 2px 4px rgba(0,0,0,0.3);
        }
        .persona-wrapper.persona-public_user .terminal-output {
            background: #f8f9fa !important;
            color: #2c3e50 !important;
            border-color: #b0bec5 !important;
            text-shadow: none;
        }
        .persona-wrapper.persona-public_user .persona-row {
            background: rgba(223, 227, 232, 0.5);
            border-color: rgba(158, 167, 176, 0.4);
        }
        .persona-wrapper.persona-public_user .persona-chip {
            background: rgba(248, 249, 250, 0.8);
            border-color: #b0bec5;
        }
        .persona-wrapper.persona-public_user .persona-chip__name {
            color: #5a6a7a;
        }
        .persona-wrapper.persona-public_user .persona-chip__desc {
            color: #7a8a9a;
        }
        .persona-wrapper.persona-public_user .screw {
            background: radial-gradient(circle at 30% 30%, #b0bec5 0%, #8b9aa8 50%, #6a7888 100%);
        }
        .persona-wrapper.persona-public_user .screw::before {
            color: #4a5a6a;
        }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''


def env_int(name, default=None):
    """Read an environment variable as int with a fallback."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_float(name, default=None):
    """Read an environment variable as float with a fallback."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def env_bool(name, default=False):
    """Read an environment variable as boolean."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_proxy_config(prefix, *, defaults=None):
    """Build reverse proxy configuration from environment variables."""
    defaults = defaults or {}
    base = prefix.upper()
    config = {
        "env_prefix": f"{base}_PROXY",
        "host": os.environ.get(f"{base}_PROXY_HOST", defaults.get("host")),
        "user": os.environ.get(f"{base}_PROXY_USER", defaults.get("user")),
        "remote_port": env_int(f"{base}_PROXY_REMOTE_PORT", defaults.get("remote_port")),
        "bind_address": os.environ.get(
            f"{base}_PROXY_BIND", defaults.get("bind_address", "0.0.0.0")
        ),
        "ssh_key_path": os.environ.get(
            f"{base}_PROXY_KEY_PATH", defaults.get("ssh_key_path")
        ),
        "keepalive_interval": env_int(
            f"{base}_PROXY_KEEPALIVE_INTERVAL", defaults.get("keepalive_interval", 30)
        ),
        "keepalive_count": env_int(
            f"{base}_PROXY_KEEPALIVE_COUNT", defaults.get("keepalive_count", 3)
        ),
        "healthcheck_interval": env_int(
            f"{base}_PROXY_HEALTH_INTERVAL", defaults.get("healthcheck_interval", 30)
        ),
        "healthcheck_timeout": env_float(
            f"{base}_PROXY_HEALTH_TIMEOUT", defaults.get("healthcheck_timeout", 2.0)
        ),
        "healthcheck_enabled": env_bool(
            f"{base}_PROXY_HEALTH_ENABLED", defaults.get("healthcheck_enabled", True)
        ),
        "healthcheck_host": os.environ.get(
            f"{base}_PROXY_HEALTH_HOST", defaults.get("healthcheck_host")
        ),
        "ssh_args": list(defaults.get("ssh_args", [])),
    }

    raw_args = os.environ.get(f"{base}_PROXY_SSH_ARGS")
    if raw_args:
        config["ssh_args"] = shlex.split(raw_args)

    config["configured"] = all(
        [config.get("host"), config.get("user"), config.get("remote_port") is not None]
    )
    return config


def _find_pids_listening_on_port(port):
    """Return a set of process IDs currently bound to a local TCP port."""
    pids = set()
    try:
        for conn in psutil.net_connections(kind='inet'):
            laddr = getattr(conn, "laddr", None)
            if not laddr:
                continue
            if getattr(laddr, "port", None) != port:
                continue
            if conn.pid:
                pids.add(conn.pid)
    except psutil.AccessDenied:
        pass
    except psutil.Error:
        return set()

    if pids:
        return pids

    # Fallback: iterate processes we can access
    try:
        for proc in psutil.process_iter(['pid']):
            pid = proc.info.get('pid')
            if pid is None:
                continue
            try:
                for conn in proc.connections(kind='inet'):
                    laddr = getattr(conn, "laddr", None)
                    if not laddr:
                        continue
                    if getattr(laddr, "port", None) != port:
                        continue
                    pids.add(pid)
                    break
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
    except psutil.Error:
        return pids
    return pids


def kill_processes_by_port(port, *, exclude_pids=None):
    """Force kill any processes listening on the specified port."""
    exclude = set(exclude_pids or [])
    target_pids = _find_pids_listening_on_port(port) - exclude
    killed = []
    for pid in target_pids:
        try:
            proc = psutil.Process(pid)
            proc.kill()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                pass
            killed.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed

# Base directory - where the managed apps are located
# For distributions, point this to the original GUI_and_components folder
# or set CONTROL_PANEL_APPS_DIR environment variable
BASE_DIR = Path(os.environ.get(
    "CONTROL_PANEL_APPS_DIR",
    "/Users/gunnarkleemann/Library/CloudStorage/GoogleDrive-gunnar@austincapitaldata.com/Shared drives/ACD curriculum/SOPs_and_tools/GUI_and_components"
))


def load_config():
    """Load application configuration from YAML file."""
    config_path = Path(__file__).parent / "apps_config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Please create apps_config.yaml in the control_panel directory."
        )
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Convert relative paths to absolute Path objects
    for tool in config.get('python_tools', []):
        tool['path'] = BASE_DIR / tool['path']
    
    for app in config.get('dash_apps', []):
        app['path'] = BASE_DIR / app['path']
        # Build reverse_proxy config from YAML structure
        if 'reverse_proxy' in app:
            rp = app['reverse_proxy']
            app['reverse_proxy'] = build_proxy_config(
                rp['env_prefix'],
                defaults={'remote_port': rp['remote_port']}
            )
    
    # Build personas from config
    personas = {}
    for persona_id, persona_data in config.get('personas', {}).items():
        personas[persona_id] = {
            "id": persona_id,
            "name": persona_data['name'],
            "description": persona_data.get('description', ''),
            "theme_class": f"persona-{persona_id}",
            "allowed_tools": persona_data.get('allowed_tools', []),
            "allowed_dash_apps": persona_data.get('allowed_dash_apps', []),
        }
    
    return config, personas


# Load configuration from YAML
config, PERSONAS = load_config()
PYTHON_TOOLS = config['python_tools']
DASH_APPS = config['dash_apps']

TOOL_LOOKUP = {tool["id"]: tool for tool in PYTHON_TOOLS}
DASH_LOOKUP = {app["id"]: app for app in DASH_APPS}

DEFAULT_PERSONA_ID = os.environ.get("CONTROL_PANEL_DEFAULT_PERSONA", "admin").lower()
if DEFAULT_PERSONA_ID not in PERSONAS:
    DEFAULT_PERSONA_ID = "admin"

ALLOW_PERSONA_SWITCH = env_bool("CONTROL_PANEL_ALLOW_PERSONA_SWITCH", True)

PERSONA_OPTIONS = [
    {"label": data["name"], "value": persona_id}
    for persona_id, data in PERSONAS.items()
]


def get_persona(persona_id):
    """Return a persona configuration by id with admin fallback."""
    if persona_id in PERSONAS:
        return PERSONAS[persona_id]
    return PERSONAS["admin"]

# Global state management
app_processes = {}
app_outputs = {}
app_status = {}
proxy_processes = {}
proxy_status = {}
proxy_health = {}
proxy_last_check = {}

def init_state():
    """Initialize global state for all apps"""
    for tool in PYTHON_TOOLS:
        app_processes[tool["id"]] = None
        app_outputs[tool["id"]] = []
        app_status[tool["id"]] = "stopped"
    
    for app_config in DASH_APPS:
        app_processes[app_config["id"]] = None
        app_outputs[app_config["id"]] = []
        app_status[app_config["id"]] = "stopped"
        proxy_processes[app_config["id"]] = None
        proxy_status[app_config["id"]] = "inactive"
        proxy_cfg = app_config.get("reverse_proxy") or {}
        if proxy_cfg.get("configured"):
            proxy_health[app_config["id"]] = {"state": "inactive", "message": "Tunnel offline"}
        else:
            env_hint = proxy_cfg.get("env_prefix", app_config["id"].upper())
            proxy_health[app_config["id"]] = {
                "state": "disabled",
                "message": f"Set {env_hint}_HOST/{env_hint}_USER/{env_hint}_REMOTE_PORT to enable"
            }
        proxy_last_check[app_config["id"]] = 0

init_state()

def read_output(process, app_id):
    """Read process output in a separate thread"""
    try:
        for line in iter(process.stdout.readline, b''):
            if line:
                decoded = line.decode('utf-8').strip()
                app_outputs[app_id].append(f"[{datetime.now().strftime('%H:%M:%S')}] {decoded}")
                # Keep only last 100 lines
                if len(app_outputs[app_id]) > 100:
                    app_outputs[app_id] = app_outputs[app_id][-100:]
    except Exception as e:
        app_outputs[app_id].append(f"[ERROR] {str(e)}")

def start_python_tool(tool_id):
    """Start a Python tool"""
    tool = next((t for t in PYTHON_TOOLS if t["id"] == tool_id), None)
    if not tool:
        return False, "Tool not found"
    
    if app_processes.get(tool_id) and app_processes[tool_id].poll() is None:
        return False, "Already running"
    
    try:
        if tool["type"] == "notebook":
            return False, "Notebooks must be opened manually in Jupyter"
        
        process = subprocess.Popen(
            [sys.executable, str(tool["path"])],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=tool["path"].parent,
            bufsize=1,
            close_fds=True,
            start_new_session=True
        )
        
        app_processes[tool_id] = process
        app_status[tool_id] = "running"
        app_outputs[tool_id] = [f"[{datetime.now().strftime('%H:%M:%S')}] Started {tool['name']}"]
        
        # Start output reader thread
        thread = threading.Thread(target=read_output, args=(process, tool_id), daemon=True)
        thread.start()
        
        return True, "Started successfully"
    except Exception as e:
        return False, f"Error: {str(e)}"


def get_dash_app(app_id):
    """Return Dash app configuration by id."""
    return next((a for a in DASH_APPS if a["id"] == app_id), None)


def start_dash_app(app_id):
    """Start a Dash application"""
    app_config = get_dash_app(app_id)
    if not app_config:
        return False, "App not found"
    
    if app_processes.get(app_id) and app_processes[app_id].poll() is None:
        return False, "Already running"
    
    try:
        # Check if port is available
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                for conn in proc.connections():
                    if conn.laddr.port == app_config["port"]:
                        return False, f"Port {app_config['port']} already in use"
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
        
        env = os.environ.copy()
        # Remove Flask/Werkzeug reloader environment variables
        env.pop('WERKZEUG_SERVER_FD', None)
        env.pop('WERKZEUG_RUN_MAIN', None)
        # Set custom flag for apps to detect control panel launch
        env['LAUNCHED_FROM_CONTROL_PANEL'] = 'true'
        
        process = subprocess.Popen(
            [sys.executable, str(app_config["path"])],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=app_config["path"].parent,
            env=env,
            bufsize=1,
            close_fds=True,
            start_new_session=True
        )
        
        app_processes[app_id] = process
        app_status[app_id] = "running"
        app_outputs[app_id] = [f"[{datetime.now().strftime('%H:%M:%S')}] Started {app_config['name']} on port {app_config['port']}"]
        
        # Start output reader thread
        thread = threading.Thread(target=read_output, args=(process, app_id), daemon=True)
        thread.start()
        
        return True, "Started successfully"
    except Exception as e:
        return False, f"Error: {str(e)}"


def read_proxy_output(process, app_id):
    """Capture stdout from the reverse proxy tunnel."""
    app_outputs.setdefault(app_id, [])
    try:
        for line in iter(process.stdout.readline, b''):
            if line:
                decoded = line.decode('utf-8', errors='replace').strip()
                app_outputs[app_id].append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] [PROXY] {decoded}"
                )
                if len(app_outputs[app_id]) > 100:
                    app_outputs[app_id] = app_outputs[app_id][-100:]
    except Exception as exc:
        app_outputs[app_id].append(f"[ERROR][PROXY] {str(exc)}")


def start_reverse_proxy(app_id):
    """Start an SSH reverse proxy for a Dash application."""
    app_config = get_dash_app(app_id)
    if not app_config:
        return False, "App not found"

    proxy_cfg = app_config.get("reverse_proxy") or {}
    if not proxy_cfg.get("configured"):
        env_hint = proxy_cfg.get("env_prefix", app_config["id"].upper())
        return False, (
            f"Reverse proxy not configured. Set {env_hint}_HOST, {env_hint}_USER and "
            f"{env_hint}_REMOTE_PORT."
        )

    existing = proxy_processes.get(app_id)
    if existing and existing.poll() is None:
        return False, "Reverse proxy already active"

    if not shutil.which("ssh"):
        return False, "'ssh' command not available on PATH"

    bind_address = proxy_cfg.get("bind_address", "0.0.0.0")
    remote_port = proxy_cfg.get("remote_port")
    local_port = app_config.get("port")
    destination = f"{proxy_cfg['user']}@{proxy_cfg['host']}"

    ssh_command = ["ssh", "-o", "ExitOnForwardFailure=yes"]
    ssh_command.extend(
        [
            "-o",
            f"ServerAliveInterval={proxy_cfg.get('keepalive_interval', 30)}",
            "-o",
            f"ServerAliveCountMax={proxy_cfg.get('keepalive_count', 3)}",
        ]
    )

    key_path = proxy_cfg.get("ssh_key_path")
    if key_path:
        ssh_command.extend(["-i", os.path.expanduser(key_path)])

    for arg in proxy_cfg.get("ssh_args", []):
        ssh_command.append(arg)

    ssh_command.extend(
        [
            "-R",
            f"{bind_address}:{remote_port}:localhost:{local_port}",
            "-N",
            destination,
        ]
    )

    try:
        process = subprocess.Popen(
            ssh_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            close_fds=True,
            start_new_session=True,
        )
    except Exception as exc:
        return False, f"Proxy error: {exc}"

    proxy_processes[app_id] = process
    proxy_status[app_id] = "active"
    proxy_health[app_id] = {
        "state": "starting",
        "message": f"Establishing tunnel to {proxy_cfg['host']}:{remote_port}",
    }

    thread = threading.Thread(target=read_proxy_output, args=(process, app_id), daemon=True)
    thread.start()

    app_outputs.setdefault(app_id, [])
    app_outputs[app_id].append(
        f"[{datetime.now().strftime('%H:%M:%S')}] [PROXY] Tunnel started at {proxy_cfg['host']}:{remote_port}"
    )
    if len(app_outputs[app_id]) > 100:
        app_outputs[app_id] = app_outputs[app_id][-100:]
    return True, f"Reverse proxy established on {proxy_cfg['host']}:{remote_port}"


def stop_reverse_proxy(app_id):
    """Stop the SSH reverse proxy."""
    process = proxy_processes.get(app_id)

    if not process or process.poll() is not None:
        proxy_processes[app_id] = None
        proxy_status[app_id] = "inactive"
        proxy_health[app_id] = {"state": "inactive", "message": "Tunnel offline"}
        proxy_last_check[app_id] = 0
        return True, "Reverse proxy already stopped"

    try:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    except Exception as exc:
        return False, f"Proxy stop error: {exc}"

    proxy_processes[app_id] = None
    proxy_status[app_id] = "inactive"
    proxy_health[app_id] = {"state": "inactive", "message": "Tunnel offline"}
    proxy_last_check[app_id] = 0
    app_outputs.setdefault(app_id, [])
    app_outputs[app_id].append(
        f"[{datetime.now().strftime('%H:%M:%S')}] [PROXY] Tunnel stopped"
    )
    if len(app_outputs[app_id]) > 100:
        app_outputs[app_id] = app_outputs[app_id][-100:]
    return True, "Reverse proxy stopped"


def update_proxy_health(app_id, *, force=False):
    """Refresh the recorded health of the reverse proxy tunnel."""
    app_config = get_dash_app(app_id)
    proxy_cfg = app_config.get("reverse_proxy") if app_config else None
    if not proxy_cfg:
        proxy_health[app_id] = {"state": "disabled", "message": "Reverse proxy unavailable"}
        return

    process = proxy_processes.get(app_id)
    if not process or process.poll() is not None:
        if proxy_cfg.get("configured"):
            exit_code = process.poll() if process else None
            if exit_code not in (None, 0) and proxy_status.get(app_id) == "active":
                proxy_health[app_id] = {
                    "state": "error",
                    "message": f"Tunnel exited (code {exit_code})",
                }
            elif not proxy_health.get(app_id):
                proxy_health[app_id] = {"state": "inactive", "message": "Tunnel offline"}
            else:
                proxy_health[app_id]["state"] = "inactive"
                proxy_health[app_id]["message"] = "Tunnel offline"
        else:
            env_hint = proxy_cfg.get("env_prefix", app_id.upper())
            proxy_health[app_id] = {
                "state": "disabled",
                "message": f"Set {env_hint}_HOST/{env_hint}_USER/{env_hint}_REMOTE_PORT",
            }
        proxy_status[app_id] = "inactive"
        return

    proxy_status[app_id] = "active"
    interval = proxy_cfg.get("healthcheck_interval", 30)
    now = time.time()
    if not force and now - proxy_last_check.get(app_id, 0) < interval:
        return

    proxy_last_check[app_id] = now

    if not proxy_cfg.get("healthcheck_enabled", True):
        proxy_health[app_id] = {"state": "active", "message": "Health check disabled"}
        return

    target_host = proxy_cfg.get("healthcheck_host") or proxy_cfg.get("host")
    remote_port = proxy_cfg.get("remote_port")
    if not target_host or remote_port is None:
        proxy_health[app_id] = {"state": "active", "message": "Health target undefined"}
        return

    timeout = proxy_cfg.get("healthcheck_timeout", 2.0)
    try:
        with socket.create_connection((target_host, remote_port), timeout=timeout):
            proxy_health[app_id] = {
                "state": "healthy",
                "message": f"{target_host}:{remote_port} reachable",
            }
    except OSError as exc:
        proxy_health[app_id] = {
            "state": "degraded",
            "message": f"Health probe failed ({exc.__class__.__name__})",
        }

def stop_app(app_id):
    """Stop an application"""
    process = app_processes.get(app_id)
    if not process or process.poll() is not None:
        return False, "Not running"
    
    try:
        # Try graceful shutdown first
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if needed
            process.kill()
            process.wait()
        
        app_processes[app_id] = None
        app_status[app_id] = "stopped"
        app_outputs[app_id].append(f"[{datetime.now().strftime('%H:%M:%S')}] Stopped")
        return True, "Stopped successfully"
    except Exception as e:
        return False, f"Error: {str(e)}"


def force_kill_app(app_id):
    """Aggressively kill an application process and release its port."""
    process = app_processes.get(app_id)
    app_config = get_dash_app(app_id)
    port = app_config.get("port") if app_config else None

    killed_pids = []
    log_messages = []

    if process and process.poll() is None:
        try:
            pid = process.pid
            process.kill()
            process.wait(timeout=5)
            killed_pids.append(pid)
            log_messages.append(f"Terminated tracked PID {pid}")
        except Exception as exc:
            return False, f"Force kill error: {exc}"
    else:
        log_messages.append("Tracked process already stopped")

    app_processes[app_id] = None
    app_status[app_id] = "stopped"

    if port:
        rogue_pids = kill_processes_by_port(port, exclude_pids=killed_pids)
        if rogue_pids:
            killed_pids.extend(rogue_pids)
            joined = ", ".join(str(pid) for pid in rogue_pids)
            log_messages.append(f"Cleared rogue PID(s) {joined} on port {port}")

    if app_id in proxy_processes:
        stop_reverse_proxy(app_id)

    app_outputs.setdefault(app_id, [])
    timestamp = datetime.now().strftime('%H:%M:%S')
    for message in log_messages:
        app_outputs[app_id].append(f"[{timestamp}] [KILL] {message}")
    if len(app_outputs[app_id]) > 100:
        app_outputs[app_id] = app_outputs[app_id][-100:]

    if killed_pids:
        summary = ", ".join(str(pid) for pid in killed_pids)
        return True, f"Force killed PID(s): {summary}"
    return False, "No matching process found on tracked PID or port"

def get_app_url(app_id):
    """Get the URL for a Dash app"""
    app_config = next((a for a in DASH_APPS if a["id"] == app_id), None)
    if app_config:
        return f"http://localhost:{app_config['port']}"
    return None

# Layout
def create_screw():
    """Create a decorative screw element"""
    return html.Div(className="screw")

def create_tool_card(tool):
    """Create a military-style gauge panel for a Python tool"""
    return html.Div([
        # Corner screws
        html.Div(className="screw screw-tl"),
        html.Div(className="screw screw-tr"),
        html.Div(className="screw screw-bl"),
        html.Div(className="screw screw-br"),
        
        # Main gauge panel content
        html.Div([
            # Label plate
            html.Div([
                html.Span(tool["name"], className="label-plate")
            ], className="mb-3"),
            
            # Control row
            dbc.Row([
                # Toggle switch section
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.Div(className="control-knob me-3", style={"verticalAlign": "middle"}),
                            html.Div([
                                dbc.Switch(
                                    id={"type": "tool-checkbox", "index": tool["id"]},
                                    value=False,
                                    className="mb-0",
                                    style={"transform": "scale(1.8)"}
                                ),
                                html.Div("POWER", className="status-text mt-1")
                            ], className="toggle-base text-center")
                        ], className="d-flex align-items-center")
                    ])
                ], width=4),
                
                # Status indicator section
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.Span(
                                "●",
                                id={"type": "tool-indicator", "index": tool["id"]},
                                style={"color": "#333", "fontSize": "28px"}
                            )
                        ], className="indicator-housing"),
                        html.Div("STATUS", className="status-text mt-1")
                    ], className="text-center")
                ], width=4),
                
                # Info section
                dbc.Col([
                    html.Div([
                        html.Small(tool["description"], style={"color": "#888", "fontFamily": "'Courier New', monospace", "fontSize": "11px"})
                    ])
                ], width=4)
            ], className="align-items-center"),
            
            # Warning stripe
            html.Div(className="warning-stripe mt-3"),

            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        "⚠ FORCE KILL",
                        id={"type": "tool-kill", "index": tool["id"]},
                        color="danger",
                        size="sm",
                        className="kill-button w-100"
                    )
                ], width=12)
            ], className="mt-2"),
            
            # Output terminal
            dbc.Collapse([
                html.Div([
                    html.Div([
                        html.Span("◀ ", style={"color": "#d4a017"}),
                        html.Span("TERMINAL OUTPUT", className="status-text"),
                        html.Span(" ▶", style={"color": "#d4a017"})
                    ], className="text-center mb-2"),
                    html.Div(
                        id={"type": "tool-output", "index": tool["id"]},
                        className="terminal-output",
                        style={
                            "padding": "12px",
                            "borderRadius": "4px",
                            "fontSize": "11px",
                            "maxHeight": "150px",
                            "overflowY": "auto",
                            "whiteSpace": "pre-wrap"
                        }
                    )
                ], className="mt-3")
            ], id={"type": "tool-collapse", "index": tool["id"]}, is_open=False)
        ], className="p-3")
    ], className="gauge-panel military-panel mb-4", style={"position": "relative", "padding": "30px"})

def create_dash_app_card(app_config):
    """Create a military-style gauge panel for a Dash application"""
    proxy_cfg = app_config.get("reverse_proxy") or {}
    proxy_ready = proxy_cfg.get("configured", False)
    proxy_env_hint = proxy_cfg.get("env_prefix", app_config["id"].upper())
    initial_proxy_message = (
        "Tunnel offline"
        if proxy_ready
        else f"Set {proxy_env_hint}_HOST/USER/REMOTE_PORT to enable"
    )
    proxy_tooltip = None if proxy_ready else f"Configure {proxy_env_hint}_* variables to enable"
    return html.Div([
        # Corner screws
        html.Div(className="screw screw-tl"),
        html.Div(className="screw screw-tr"),
        html.Div(className="screw screw-bl"),
        html.Div(className="screw screw-br"),
        
        # Main gauge panel content
        html.Div([
            # Label plate with port number
            html.Div([
                html.Span(app_config["name"], className="label-plate me-2"),
                html.Span(f"PORT {app_config['port']}", 
                         style={"color": "#00ff00", "fontFamily": "'Courier New', monospace", 
                                "fontSize": "12px", "backgroundColor": "#111", 
                                "padding": "4px 8px", "borderRadius": "3px",
                                "border": "1px solid #00ff00"})
            ], className="mb-3 d-flex align-items-center"),
            
            # Control row
            dbc.Row([
                # Toggle switch section
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.Div(className="control-knob me-3", style={"verticalAlign": "middle"}),
                            html.Div([
                                dbc.Switch(
                                    id={"type": "dash-checkbox", "index": app_config["id"]},
                                    value=False,
                                    className="mb-0",
                                    style={"transform": "scale(1.8)"}
                                ),
                                html.Div("IGNITION", className="status-text mt-1")
                            ], className="toggle-base text-center")
                        ], className="d-flex align-items-center")
                    ])
                ], width=3),
                
                # Status indicator section
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.Span(
                                "●",
                                id={"type": "dash-indicator", "index": app_config["id"]},
                                style={"color": "#333", "fontSize": "28px"}
                            )
                        ], className="indicator-housing"),
                        html.Div("REACTOR", className="status-text mt-1")
                    ], className="text-center")
                ], width=2),
                
                # Open link as big button
                dbc.Col([
                    html.A(
                        html.Div([
                            html.Div("▶ LAUNCH", style={"fontWeight": "bold", "fontSize": "14px"}),
                            html.Div("INTERFACE", className="status-text")
                        ], className="text-center"),
                        id={"type": "dash-open", "index": app_config["id"]},
                        href=f"http://localhost:{app_config['port']}",
                        target="_blank",
                        style={
                            "display": "block",
                            "background": "linear-gradient(180deg, #4a4a4a, #2a2a2a)",
                            "border": "3px solid #555",
                            "borderRadius": "6px",
                            "padding": "10px 20px",
                            "color": "#666",
                            "textDecoration": "none",
                            "pointerEvents": "none",
                            "opacity": "0.5",
                            "cursor": "not-allowed",
                            "boxShadow": "inset 0 2px 4px rgba(0,0,0,0.3)"
                        }
                    )
                ], width=3),
                
                # Description
                dbc.Col([
                    html.Div([
                        html.Small(app_config["description"], 
                                  style={"color": "#888", "fontFamily": "'Courier New', monospace", "fontSize": "11px"})
                    ])
                ], width=4)
            ], className="align-items-center"),

            # Reverse proxy controls + kill radio
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Div([
                            dbc.Switch(
                                id={"type": "proxy-checkbox", "index": app_config["id"]},
                                value=False,
                                className="mb-0",
                                style={"transform": "scale(1.5)"},
                                disabled=not proxy_ready,
                            ),
                            html.Div("PROXY", className="status-text mt-1")
                        ], className="toggle-base text-center", title=proxy_tooltip)
                    ])
                ], width=3),

                dbc.Col([
                    html.Div([
                        html.Div([
                            html.Span(
                                "●",
                                id={"type": "proxy-indicator", "index": app_config["id"]},
                                style={"color": "#333", "fontSize": "24px"}
                            )
                        ], className="indicator-housing"),
                        html.Div("TUNNEL", className="status-text mt-1")
                    ], className="text-center")
                ], width=2),

                dbc.Col([
                    html.Div(
                        id={"type": "proxy-status", "index": app_config["id"]},
                        className="status-text",
                        style={"minHeight": "28px"},
                        children=initial_proxy_message
                    )
                ], width=5),

                dbc.Col([
                    html.Div([
                        html.Div("KILL SWITCH", className="status-text mb-1"),
                        dbc.RadioItems(
                            id={"type": "dash-kill", "index": app_config["id"]},
                            options=[
                                {"label": "ARM", "value": "safe"},
                                {"label": "PURGE", "value": "purge"}
                            ],
                            value="safe",
                            className="kill-radio",
                            inline=False,
                        )
                    ], className="text-center")
                ], width=2)
            ], className="align-items-center mt-3"),
            
            # Rivets decoration
            html.Div([
                html.Span(className="rivet"),
                html.Span(className="rivet"),
                html.Span(className="rivet"),
                html.Span("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", style={"color": "#444", "fontSize": "8px", "letterSpacing": "-2px"}),
                html.Span(className="rivet"),
                html.Span(className="rivet"),
                html.Span(className="rivet")
            ], className="text-center mt-3"),
            
            # Output terminal
            dbc.Collapse([
                html.Div([
                    html.Div([
                        html.Span("◀ ", style={"color": "#d4a017"}),
                        html.Span("SYSTEM LOG", className="status-text"),
                        html.Span(" ▶", style={"color": "#d4a017"})
                    ], className="text-center mb-2"),
                    html.Div(
                        id={"type": "dash-output", "index": app_config["id"]},
                        className="terminal-output",
                        style={
                            "padding": "12px",
                            "borderRadius": "4px",
                            "fontSize": "11px",
                            "maxHeight": "150px",
                            "overflowY": "auto",
                            "whiteSpace": "pre-wrap"
                        }
                    )
                ], className="mt-3")
            ], id={"type": "dash-collapse", "index": app_config["id"]}, is_open=False)
        ], className="p-3")
    ], className="gauge-panel military-panel mb-4", style={"position": "relative", "padding": "30px"})


def _render_empty_panel(message):
    """Display a themed alert when a persona has no panels for a section."""
    return dbc.Alert(
        message,
        color="secondary",
        className="persona-empty-alert",
        style={"fontFamily": "'Courier New', monospace", "fontSize": "12px"},
    )


def build_tool_cards(tool_ids):
    """Render only the tool cards assigned to the active persona."""
    cards = []
    for tool_id in tool_ids:
        tool_cfg = TOOL_LOOKUP.get(tool_id)
        if tool_cfg:
            cards.append(create_tool_card(tool_cfg))
    if cards:
        return cards
    return [_render_empty_panel("No utility systems assigned to this persona.")]


def build_dash_cards(app_ids):
    """Render only the Dash cards assigned to the active persona."""
    cards = []
    for app_id in app_ids:
        app_cfg = DASH_LOOKUP.get(app_id)
        if app_cfg:
            cards.append(create_dash_app_card(app_cfg))
    if cards:
        return cards
    return [_render_empty_panel("No reactors available for this persona.")]


initial_persona = get_persona(DEFAULT_PERSONA_ID)
initial_tool_children = build_tool_cards(initial_persona["allowed_tools"])
initial_dash_children = build_dash_cards(initial_persona["allowed_dash_apps"])
initial_active_tab = "tools" if initial_persona["allowed_tools"] else "dash-apps"
persona_switch_style = {} if ALLOW_PERSONA_SWITCH else {"display": "none"}
initial_persona_chip = [
    html.Span("PERSONA", className="status-text me-2"),
    html.Span(initial_persona["name"], className="persona-chip__name"),
    html.Span(initial_persona["description"], className="persona-chip__desc ms-2"),
]


app.layout = html.Div([
    dcc.Store(id="active-persona", data=initial_persona["id"]),
    dbc.Container([
        # Main console panel
        html.Div([
            # Corner screws for main panel
            html.Div(className="screw screw-tl"),
            html.Div(className="screw screw-tr"),
            html.Div(className="screw screw-bl"),
            html.Div(className="screw screw-br"),

            # Console header
            html.Div([
                html.Div([
                    html.Span(className="rivet"),
                    html.Span(className="rivet"),
                    html.Span(className="rivet"),
                ], className="mb-2"),
                html.H1("⚙️ CONTROL STATION", className="console-title mb-1"),
                html.Div(
                    "SYSTEM MANAGEMENT INTERFACE v2.0",
                    style={
                        "color": "#888",
                        "fontFamily": "'Courier New', monospace",
                        "fontSize": "12px",
                        "letterSpacing": "2px",
                    },
                ),
                html.Div([
                    html.Span(className="rivet"),
                    html.Span(className="rivet"),
                    html.Span(className="rivet"),
                ], className="mt-2"),
            ], className="console-header"),

            # Persona control row
            html.Div([
                html.Div([
                    html.Div(
                        initial_persona_chip,
                        id="persona-chip",
                        className="persona-chip",
                    )
                ], className="flex-grow-1"),
                html.Div([
                    dbc.Label("Persona Switch", className="status-text mb-1"),
                    dbc.Select(
                        id="persona-select",
                        options=PERSONA_OPTIONS,
                        value=initial_persona["id"],
                        disabled=not ALLOW_PERSONA_SWITCH,
                        className="persona-select-control",
                    ),
                ], className="persona-selector", style=persona_switch_style),
            ], className="persona-row d-flex flex-column flex-md-row align-items-md-center gap-3"),

            # Warning stripe
            html.Div(className="warning-stripe mb-4"),

            # Tabs styled as panel sections
            dbc.Tabs([
                dbc.Tab(
                    [
                        html.Div([
                            html.Span("◈", style={"color": "#d4a017", "fontSize": "20px"}),
                            html.Span(" UTILITY SYSTEMS ", className="label-plate mx-2"),
                            html.Span("◈", style={"color": "#d4a017", "fontSize": "20px"}),
                        ], className="text-center mb-4 mt-3"),
                        html.Div(initial_tool_children, id="tool-card-container"),
                    ],
                    label="⚡ UTILITIES",
                    tab_id="tools",
                    id="tools-tab",
                    label_style={
                        "fontFamily": "'Courier New', monospace",
                        "fontWeight": "bold",
                    },
                ),

                dbc.Tab(
                    [
                        html.Div([
                            html.Span("◈", style={"color": "#d4a017", "fontSize": "20px"}),
                            html.Span(
                                " APPLICATION REACTORS ",
                                className="label-plate mx-2",
                            ),
                            html.Span("◈", style={"color": "#d4a017", "fontSize": "20px"}),
                        ], className="text-center mb-3 mt-3"),

                        # Technical note alert
                        dbc.Alert(
                            [
                                html.Div(
                                    [
                                        html.Strong(
                                            "⚠ OPERATOR NOTICE: ",
                                            style={"color": "#d4a017"},
                                        ),
                                        html.Span(
                                            "Applications run in isolated subprocess mode. ",
                                            style={"color": "#ccc"},
                                        ),
                                        html.Span(
                                            "Flask reloader disabled (WERKZEUG_RUN_MAIN=true). ",
                                            style={"color": "#888", "fontSize": "11px"},
                                        ),
                                        html.Span(
                                            "Hot-reload unavailable when launched from Control Station.",
                                            style={"color": "#888", "fontSize": "11px"},
                                        ),
                                    ],
                                    style={
                                        "fontFamily": "'Courier New', monospace",
                                        "fontSize": "12px",
                                    },
                                )
                            ],
                            color="dark",
                            className="mb-4",
                            style={
                                "backgroundColor": "#1a1a1a",
                                "border": "2px solid #d4a017",
                                "borderRadius": "4px",
                            },
                        ),

                        html.Div(initial_dash_children, id="dash-card-container"),
                    ],
                    label="🚀 REACTORS",
                    tab_id="dash-apps",
                    id="dash-tab",
                    label_style={
                        "fontFamily": "'Courier New', monospace",
                        "fontWeight": "bold",
                    },
                ),
            ], id="tabs", active_tab=initial_active_tab, className="mb-4"),

            # Footer with status
            html.Div([
                html.Div(className="warning-stripe mb-3"),
                html.Div([
                    html.Span("STATION OPERATIONAL", className="status-text me-3"),
                    html.Span("●", style={"color": "#00ff00", "fontSize": "12px"}),
                    html.Span(" │ ", style={"color": "#444"}),
                    html.Span("PORT 8060", className="status-text"),
                ], className="text-center"),
            ], className="mt-4"),
        ], className="military-panel p-4", style={"position": "relative", "marginTop": "20px"}),

        dcc.Interval(id="status-update", interval=2000, n_intervals=0),
    ], fluid=True, className="p-4"),
], id="persona-root", className=f"persona-wrapper {initial_persona['theme_class']}")

# Callbacks


@callback(
    Output("active-persona", "data"),
    Output("persona-root", "className"),
    Output("tool-card-container", "children"),
    Output("dash-card-container", "children"),
    Output("persona-chip", "children"),
    Output("tabs", "active_tab"),
    Input("persona-select", "value"),
    prevent_initial_call=False,
)
def update_persona_view(selected_persona):
    """Swap themes and visible panels when the persona selector changes."""
    persona_key = (selected_persona or DEFAULT_PERSONA_ID).lower()
    persona = get_persona(persona_key)

    tool_children = build_tool_cards(persona["allowed_tools"])
    dash_children = build_dash_cards(persona["allowed_dash_apps"])
    persona_chip = [
        html.Span("PERSONA", className="status-text me-2"),
        html.Span(persona["name"], className="persona-chip__name"),
        html.Span(persona["description"], className="persona-chip__desc ms-2"),
    ]
    root_class = f"persona-wrapper {persona['theme_class']}"
    active_tab = "tools" if persona["allowed_tools"] else "dash-apps"

    return (
        persona["id"],
        root_class,
        tool_children,
        dash_children,
        persona_chip,
        active_tab,
    )


@callback(
    Output({"type": "tool-collapse", "index": MATCH}, "is_open"),
    Output({"type": "tool-indicator", "index": MATCH}, "style"),
    Output({"type": "tool-output", "index": MATCH}, "children"),
    Input({"type": "tool-checkbox", "index": MATCH}, "value"),
    Input({"type": "tool-kill", "index": MATCH}, "n_clicks"),
    Input("status-update", "n_intervals"),
    State({"type": "tool-checkbox", "index": MATCH}, "id"),
    prevent_initial_call=False
)
def handle_python_tool(checked, kill_clicks, n, tool_id_dict):
    """Handle Python tool checkbox and status updates"""
    tool_id = tool_id_dict["index"]
    triggered_id = ctx.triggered_id
    
    # Handle checkbox toggle
    if triggered_id and isinstance(triggered_id, dict) and triggered_id.get("type") == "tool-checkbox":
        if checked:
            success, message = start_python_tool(tool_id)
            if not success:
                app_outputs[tool_id].append(f"[ERROR] {message}")
        else:
            stop_app(tool_id)
    elif triggered_id and isinstance(triggered_id, dict) and triggered_id.get("type") == "tool-kill":
        success, message = force_kill_app(tool_id)
        if not success:
            app_outputs.setdefault(tool_id, [])
            app_outputs[tool_id].append(f"[{datetime.now().strftime('%H:%M:%S')}] [KILL][WARN] {message}")
            if len(app_outputs[tool_id]) > 100:
                app_outputs[tool_id] = app_outputs[tool_id][-100:]
    
    # Update status
    is_running = app_status.get(tool_id) == "running"
    indicator_style = {
        "color": "#00ff00" if is_running else "#333",
        "fontSize": "28px",
        "textShadow": "0 0 10px rgba(0,255,0,0.8)" if is_running else "none"
    }
    
    output_text = "\n".join(app_outputs.get(tool_id, ["No output yet"]))
    
    return checked and True, indicator_style, output_text

@callback(
    Output({"type": "dash-collapse", "index": MATCH}, "is_open"),
    Output({"type": "dash-indicator", "index": MATCH}, "style"),
    Output({"type": "dash-open", "index": MATCH}, "style"),
    Output({"type": "dash-output", "index": MATCH}, "children"),
    Output({"type": "proxy-indicator", "index": MATCH}, "style"),
    Output({"type": "proxy-status", "index": MATCH}, "children"),
    Output({"type": "dash-kill", "index": MATCH}, "value"),
    Input({"type": "dash-checkbox", "index": MATCH}, "value"),
    Input({"type": "proxy-checkbox", "index": MATCH}, "value"),
    Input({"type": "dash-kill", "index": MATCH}, "value"),
    Input("status-update", "n_intervals"),
    State({"type": "dash-checkbox", "index": MATCH}, "id"),
    prevent_initial_call=False
)
def handle_dash_app(checked, proxy_checked, kill_value, n, app_id_dict):
    """Handle Dash app checkbox and status updates"""
    app_id = app_id_dict["index"]
    triggered_id = ctx.triggered_id
    proxy_checked = bool(proxy_checked)
    kill_value_reset = no_update
    app_config = get_dash_app(app_id)
    
    # Handle checkbox toggle
    if triggered_id and isinstance(triggered_id, dict) and triggered_id.get("type") == "dash-checkbox":
        if checked:
            success, message = start_dash_app(app_id)
            if not success:
                app_outputs[app_id].append(f"[ERROR] {message}")
        else:
            stop_app(app_id)
    elif triggered_id and isinstance(triggered_id, dict) and triggered_id.get("type") == "proxy-checkbox":
        if proxy_checked:
            success, message = start_reverse_proxy(app_id)
        else:
            success, message = stop_reverse_proxy(app_id)
        if not success:
            app_outputs.setdefault(app_id, [])
            app_outputs[app_id].append(
                f"[{datetime.now().strftime('%H:%M:%S')}] [PROXY][ERROR] {message}"
            )
            if len(app_outputs[app_id]) > 100:
                app_outputs[app_id] = app_outputs[app_id][-100:]
    elif triggered_id and isinstance(triggered_id, dict) and triggered_id.get("type") == "dash-kill":
        if kill_value == "purge":
            success, message = force_kill_app(app_id)
            if not success:
                app_outputs.setdefault(app_id, [])
                app_outputs[app_id].append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] [KILL][WARN] {message}"
                )
                if len(app_outputs[app_id]) > 100:
                    app_outputs[app_id] = app_outputs[app_id][-100:]
            kill_value_reset = "safe"
    
    # Update status
    is_running = app_status.get(app_id) == "running"
    indicator_style = {
        "color": "#00ff00" if is_running else "#333",
        "fontSize": "28px",
        "textShadow": "0 0 10px rgba(0,255,0,0.8)" if is_running else "none"
    }
    
    # Enable/disable link - military launch button style
    if is_running:
        link_style = {
            "display": "block",
            "background": "linear-gradient(180deg, #2a5a2a, #1a3a1a)",
            "border": "3px solid #00ff00",
            "borderRadius": "6px",
            "padding": "10px 20px",
            "color": "#00ff00",
            "textDecoration": "none",
            "pointerEvents": "auto",
            "opacity": "1",
            "cursor": "pointer",
            "boxShadow": "0 0 15px rgba(0,255,0,0.4), inset 0 2px 4px rgba(0,0,0,0.3)",
            "textShadow": "0 0 5px rgba(0,255,0,0.5)"
        }
    else:
        link_style = {
            "display": "block",
            "background": "linear-gradient(180deg, #4a4a4a, #2a2a2a)",
            "border": "3px solid #555",
            "borderRadius": "6px",
            "padding": "10px 20px",
            "color": "#666",
            "textDecoration": "none",
            "pointerEvents": "none",
            "opacity": "0.5",
            "cursor": "not-allowed",
            "boxShadow": "inset 0 2px 4px rgba(0,0,0,0.3)"
        }
    
    output_text = "\n".join(app_outputs.get(app_id, ["No output yet"]))

    # Proxy indicators
    update_proxy_health(app_id)
    proxy_state = proxy_health.get(app_id, {"state": "inactive", "message": "Tunnel offline"})
    proxy_indicator_style = {
        "color": "#333",
        "fontSize": "24px",
        "textShadow": "none",
    }

    state = proxy_state.get("state")
    if state == "healthy":
        proxy_indicator_style.update({
            "color": "#00e5ff",
            "textShadow": "0 0 12px rgba(0,229,255,0.7)",
        })
    elif state == "degraded":
        proxy_indicator_style.update({
            "color": "#ffbe0b",
            "textShadow": "0 0 10px rgba(255,190,11,0.6)",
        })
    elif state == "error":
        proxy_indicator_style.update({
            "color": "#ff3b30",
            "textShadow": "0 0 10px rgba(255,59,48,0.6)",
        })
    elif state == "starting":
        proxy_indicator_style.update({
            "color": "#00fff2",
            "textShadow": "0 0 10px rgba(0,255,242,0.5)",
        })
    elif state == "active":
        proxy_indicator_style.update({
            "color": "#1dd3b0",
            "textShadow": "0 0 10px rgba(29,211,176,0.5)",
        })
    elif state == "disabled":
        proxy_indicator_style["color"] = "#555"
    else:
        proxy_indicator_style["color"] = "#333"

    endpoint = None
    if app_config:
        proxy_cfg = app_config.get("reverse_proxy") or {}
        if proxy_cfg.get("configured"):
            endpoint = f"{proxy_cfg.get('host')}:{proxy_cfg.get('remote_port')}"
    proxy_status_text = proxy_state.get("message", "")
    if endpoint:
        proxy_status_text = f"{endpoint} • {proxy_status_text}"
    
    return (
        checked and True,
        indicator_style,
        link_style,
        output_text,
        proxy_indicator_style,
        proxy_status_text,
        kill_value_reset,
    )

if __name__ == "__main__":
    print("🎛️  Control Panel starting on http://localhost:8060")
    print("=" * 50)
    app.run(debug=True, port=8060)