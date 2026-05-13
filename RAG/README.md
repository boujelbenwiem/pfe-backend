# RAG Project Setup

## 1. Create a Virtual Environment

```powershell
cd your-project-folder
uv init --no-readme
uv venv
.venv\Scripts\activate
```

## 2. Auto-Updating requirements.txt

To automatically update `requirements.txt` every time you install a package, add these functions to your PowerShell profile.

### Open your profile

```powershell
notepad $PROFILE
```

If the file doesn't exist yet:

```powershell
New-Item -ItemType File -Path $PROFILE -Force
notepad $PROFILE
```

### Paste this into the profile

```powershell
# Auto-updating requirements.txt wrappers

function uva {
    uv add @args
    if ($LASTEXITCODE -eq 0) {
        uv export --format requirements-txt --no-hashes --quiet > requirements.txt
        Write-Host "requirements.txt updated" -ForegroundColor Green
    }
}

function pipi {
    uv pip install @args
    if ($LASTEXITCODE -eq 0) {
        uv pip freeze > requirements.txt
        Write-Host "requirements.txt updated" -ForegroundColor Green
    }
}
```

Save and close the file.

### Allow script execution (one-time)

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

### Reload the profile in current terminal

```powershell
. $PROFILE
```

## 3. Usage

| Command | What it does |
|---------|--------------|
| `uva package-name` | Runs `uv add`, then exports requirements.txt |
| `pipi package-name` | Runs `uv pip install`, then freezes requirements.txt |

These work in **any project directory** — they update `requirements.txt` in whatever folder you're currently in.

## 4. Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) must be installed (`pip install uv` or `winget install astral-sh.uv`)
- Python 3.10+
