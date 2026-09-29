#!/usr/bin/env python3
import subprocess
import datetime
import html
import sys
from weasyprint import HTML

def run_cmd(args, cwd):
    try:
        return subprocess.check_output(args, cwd=cwd, stderr=subprocess.STDOUT).decode('utf-8')
    except Exception as e:
        return f"Error running {' '.join(args)}: {e}"

CWD = "/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl"
OUT_PDF = "/home/x-root/Desktop/git_report_today.pdf"

# 1. Get commits from today
log_format = "<tr><td class='sha'>%h</td><td class='time'>%ad</td><td class='msg'>%s</td></tr>"
commits_raw = run_cmd(["git", "log", "--since=2026-07-13 00:00:00", f"--pretty=format:{log_format}", "--date=format:%H:%M:%S"], CWD)

# 2. Get git show/stat of today's changes
stat_raw = run_cmd(["git", "log", "--since=2026-07-13 00:00:00", "--stat"], CWD)

# 3. Get current git status & diff
git_status = run_cmd(["git", "status", "-s"], CWD)
git_diff = run_cmd(["git", "diff"], CWD)

now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Construct HTML
html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>MitrPhol Development Report — {now_str}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

@page {{
    size: A4;
    margin: 20mm;
    @bottom-right {{
        content: counter(page);
        font-family: 'Inter', sans-serif;
        font-size: 9px;
        color: #8b949e;
    }}
    @bottom-left {{
        content: "MitrPhol xMixing Control — Daily Report";
        font-family: 'Inter', sans-serif;
        font-size: 9px;
        color: #8b949e;
    }}
}}

body {{
    font-family: 'Inter', sans-serif;
    background-color: #ffffff;
    color: #24292f;
    line-height: 1.5;
    font-size: 11px;
}}

h1 {{
    font-size: 20px;
    font-weight: 700;
    color: #0969da;
    border-bottom: 2px solid #d0d7de;
    padding-bottom: 8px;
    margin-top: 0;
}}

h2 {{
    font-size: 14px;
    font-weight: 600;
    color: #1f2328;
    margin-top: 24px;
    margin-bottom: 8px;
    border-left: 3px solid #0969da;
    padding-left: 8px;
}}

.meta-box {{
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
}}

.meta-item {{
    font-size: 10px;
    color: #57606a;
}}

.meta-item strong {{
    color: #24292f;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16px;
}}

th, td {{
    padding: 8px;
    text-align: left;
    border-bottom: 1px solid #d0d7de;
}}

th {{
    background-color: #f6f8fa;
    font-weight: 600;
    font-size: 10px;
    color: #57606a;
}}

.sha {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    color: #0969da;
    width: 80px;
}}

.time {{
    font-size: 10px;
    color: #57606a;
    width: 80px;
}}

pre {{
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 9.5px;
    white-space: pre-wrap;
    word-break: break-all;
    margin-top: 8px;
}}

.diff-added {{
    background-color: #dafbe1;
    color: #1a7f37;
}}

.diff-removed {{
    background-color: #ffebe9;
    color: #cf222e;
}}

.alert {{
    background-color: #ddf4ff;
    border: 1px solid #54aeff66;
    border-radius: 6px;
    padding: 12px;
    color: #0969da;
    margin-bottom: 16px;
}}

.alert strong {{
    color: #0969da;
}}
</style>
</head>
<body>

<h1>📈 Daily Development & Git Integration Report</h1>
<div class="meta-box">
    <div class="meta-item">Project: <strong>x2512001 MitrPhol (xMixing)</strong></div>
    <div class="meta-item">Date: <strong>2026-07-13</strong></div>
    <div class="meta-item">Generated At: <strong>{now_str}</strong></div>
</div>

<div class="alert">
    <strong>💡 Executive Summary:</strong><br>
    Today's development focused on resolving synchronization conflicts and establishing a centralized PLC step management system:
    <ul>
        <li>Implemented the background <code>worker_step_watcher</code> service to automatically advance AUTO steps (8, 10, 28) without operator overhead.</li>
        <li>Bypassed and disabled the legacy <code>FC_MapPhaseToStep</code> logic inside the PLC's OB1 scan loop, shifting all step mapping calculations to the App's centralized logic (FastAPI sequencer and Vue HMI).</li>
        <li>Modified DB179 direct writing, ensuring the PLC always runs in sync with the central sequencer plan.</li>
        <li>Corrected the <strong>"Step 4" mapping mismatch</strong> for manual ingredient additions, shifting it to <strong>Step 14</strong> to align with the system's interlock gates.</li>
    </ul>
</div>

<h2>🧑‍💻 Git Commits Completed Today</h2>
<table>
    <thead>
        <tr>
            <th>Commit SHA</th>
            <th>Time</th>
            <th>Message</th>
        </tr>
    </thead>
    <tbody>
        {commits_raw if commits_raw else "<tr><td colspan='3' style='text-align:center;color:#57606a'>No commits today. All work is in active session.</td></tr>"}
    </tbody>
</table>

<h2>📊 Git Commit Stats & File Modifications</h2>
<pre>{html.escape(stat_raw)}</pre>

<h2>🛠️ Session Modifications (Active Fixes)</h2>
<p>The following changes were made in the latest session to correct the step mapping mismatch for Manual Additions and QC Hold:</p>
<pre><strong>Git Status:</strong><br>{html.escape(git_status)}</pre>

<h2>🔍 Git Code Diff</h2>
<pre>{html.escape(git_diff)}</pre>

</body>
</html>
"""

# Write PDF
HTML(string=html_content).write_pdf(OUT_PDF)
print(f"Successfully generated PDF: {OUT_PDF}")
print(f"Size: {len(html_content)} bytes")
