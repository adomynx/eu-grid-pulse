"""End-to-end orchestration entry point.

Thin wrapper around src.run_pipeline so `python -m src.pipeline` (as the Dockerfile
and Makefile call it) runs the real pipeline and propagates its exit code.
"""
import sys

from .run_pipeline import main

if __name__ == "__main__":
    sys.exit(main())
