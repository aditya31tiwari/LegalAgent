import os
import sys
import uvicorn
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from web.backend import app

def main():
    port = 8080
    host = "0.0.0.0"
    print("\n" + "="*70)
    print(" ⚖️   LegalAgent Enterprise Intelligence Engine")
    print(f" 🌐  Web Application  : http://localhost:{port}")
    print(f" 📚  Swagger REST API : http://localhost:{port}/docs")
    print(f" 🗄️   SQLite Database  : {PROJECT_ROOT / 'contracts.db'}")
    print("="*70 + "\n")
    uvicorn.run("web.backend:app", host=host, port=port, reload=False, log_level="info")

if __name__ == "__main__":
    main()
