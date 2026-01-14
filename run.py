#!/usr/bin/env python3
"""
LinkedIn Sales Robot - Startup Script
Run this to start the application.
"""

import subprocess
import sys
import os


def check_dependencies():
    """Check if required packages are installed"""
    try:
        import fastapi
        import uvicorn
        import playwright
        import httpx
        return True
    except ImportError as e:
        print(f"Missing dependency: {e.name}")
        print("\nPlease install dependencies first:")
        print("  pip install -r requirements.txt")
        print("  playwright install chromium")
        return False


def main():
    print("""
    ╔══════════════════════════════════════════════╗
    ║       LinkedIn Sales Robot v1.0              ║
    ║   Automated Outreach & CRM Integration       ║
    ╚══════════════════════════════════════════════╝
    """)
    
    if not check_dependencies():
        sys.exit(1)
    
    # Ensure we're in the right directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("Starting server at http://localhost:8000")
    print("Press Ctrl+C to stop\n")
    
    # Run uvicorn
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()

