# QUANT INDUSTRY Setup Guide

Complete guide to setting up and running QUANT INDUSTRY v10.0

---

## System Requirements

### Minimum Requirements
- **OS**: Windows 10/11, macOS 10.15+, or Linux
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Storage**: 10 GB free space
- **Python**: 3.10 or higher
- **Node.js**: 18.x or higher

### Recommended Requirements
- **CPU**: 8+ cores
- **RAM**: 16+ GB
- **GPU**: NVIDIA GPU with CUDA support (for ML features)
- **Storage**: SSD with 20+ GB free space

---

## Quick Start

### Windows
```batch
# Clone and enter directory
cd quant_industry_v1

# Run the launcher
START.bat
```

### macOS/Linux
```bash
# Clone and enter directory
cd quant_industry_v1

# Start backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 &

# Start frontend
cd ../frontend
npm install
npm run dev &

# Open browser
open http://localhost:3000
```

---

## Detailed Setup

### 1. Install Prerequisites

#### Python (3.10+)
```bash
# Windows (download from python.org)
# Or using winget:
winget install Python.Python.3.12

# macOS
brew install python@3.12

# Linux
sudo apt install python3.12 python3.12-venv
```

#### Node.js (18+)
```bash
# Windows
winget install OpenJS.NodeJS.LTS

# macOS
brew install node@18

# Linux
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs
```

### 2. Backend Setup

```bash
cd quant_industry_v1/backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your API keys (see API Keys section)
```

### 3. Frontend Setup

```bash
cd quant_industry_v1/frontend

# Install dependencies
npm install

# Create local environment file (optional)
cp .env.example .env.local
```

### 4. Desktop App Setup (Optional)

```bash
cd quant_industry_v1/desktop

# Install Electron dependencies
npm install
```

---

## API Keys Configuration

### Supported Data Providers

| Provider | Required | Free Tier | Documentation |
|----------|----------|-----------|---------------|
| Alpaca | Recommended | Yes | https://alpaca.markets/docs |
| Tradier | Optional | Yes | https://documentation.tradier.com |
| Yahoo Finance | Fallback | Yes | Built-in |

### Setting Up API Keys

1. Create accounts at your chosen providers
2. Generate API keys
3. Edit `backend/.env`:

```env
# Alpaca (Recommended)
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # or api.alpaca.markets for live

# Tradier (Optional)
TRADIER_API_KEY=your_api_key_here
TRADIER_ACCOUNT_ID=your_account_id

# OpenAI (Optional - for AI features)
OPENAI_API_KEY=your_api_key_here
```

### Testing API Connection

```bash
# Start the backend
cd backend
python -m uvicorn main:app --reload

# Test connection
curl http://localhost:8000/api/settings/test-connection/alpaca
```

---

## Running the Application

### Development Mode

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Terminal 3 - Desktop (Optional):**
```bash
cd desktop
npm start
```

### Production Mode

**Backend:**
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Frontend:**
```bash
cd frontend
npm run build
npm run preview
```

### Using START.bat (Windows)

The `START.bat` file automates the entire startup process:
1. Verifies prerequisites (Python, Node.js)
2. Starts the backend server
3. Waits for backend to be ready
4. Starts the frontend dev server
5. Waits for frontend to be ready
6. Launches the Electron desktop app

Just double-click `START.bat` or run from command line.

---

## Verification

### Check Backend Health
```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-24T12:00:00",
  "market": {"session": "..."}
}
```

### Check Frontend
Open http://localhost:3000 in your browser.

### Run Tests
```bash
cd backend
python -m pytest tests/ -v
```

---

## Troubleshooting

### Port Already in Use

**Error:** `Address already in use`

**Solution:**
```bash
# Find process using port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux:
lsof -i :8000
kill -9 <PID>
```

### Module Not Found

**Error:** `ModuleNotFoundError: No module named 'xxx'`

**Solution:**
```bash
cd backend
pip install -r requirements.txt
```

### API Connection Failed

**Error:** `Failed to connect to Alpaca`

**Solutions:**
1. Check API keys in `.env`
2. Verify API key permissions
3. Check network connectivity
4. Try the paper trading URL first

### Frontend Build Errors

**Error:** `npm ERR!`

**Solution:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### CUDA/GPU Issues

**Error:** `CUDA not available`

**Solutions:**
1. Install NVIDIA drivers
2. Install CUDA Toolkit
3. Install cuDNN
4. The app will fall back to CPU if GPU unavailable

---

## Configuration

### Backend Configuration

Key configuration files:
- `backend/.env` - Environment variables and API keys
- `backend/config/settings.py` - Application settings
- `backend/config/api_keys.py` - API key management

### Frontend Configuration

Key configuration files:
- `frontend/.env.local` - Local environment overrides
- `frontend/vite.config.ts` - Vite configuration

### Available Settings

Access settings via the UI or API:
- Theme preferences
- Trading parameters
- Risk limits
- Alert thresholds
- Data refresh intervals

---

## Updating

### Backend Update
```bash
cd backend
git pull
pip install -r requirements.txt --upgrade
```

### Frontend Update
```bash
cd frontend
git pull
npm install
npm run build
```

---

## Getting Help

- **API Documentation**: http://localhost:8000/docs
- **GitHub Issues**: https://github.com/anthropics/claude-code/issues
- **Logs**: Check `backend/logs/` for detailed error logs
