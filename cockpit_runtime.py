"""Legacy entry point. The company cockpit now lives in app.py."""
from pathlib import Path
import runpy


def render_cockpit(**kwargs):
    return runpy.run_path(str(Path(__file__).with_name("app.py")), run_name="__main__")
