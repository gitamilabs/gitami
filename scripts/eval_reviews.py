"""Root wrapper for GitAmi PR review evaluation harness."""

import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent
ai_service_dir = root_dir / "backend" / "ai-service"
script_path = ai_service_dir / "scripts" / "eval_reviews.py"

if not script_path.exists():
    print(f"Error: {script_path} not found.")
    sys.exit(1)

# Ensure ai_service src is in path
sys.path.insert(0, str(ai_service_dir / "src"))

import importlib.util
spec = importlib.util.spec_from_file_location("eval_reviews", str(script_path))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == "__main__":
    module.main()
