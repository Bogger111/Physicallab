#!/usr/bin/env python3
"""Run PhysicsLab backend server."""
import uvicorn
import sys
import os

# Ensure experiments module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[os.path.dirname(os.path.abspath(__file__))],
    )
