#!/usr/bin/env python
"""Simple server starter that ensures correct working directory"""
import os
import sys

# Change to the backend directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

print(f"Starting from: {os.getcwd()}")

# Start uvicorn
import uvicorn

uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
