"""Run the Flask app. Use: python run_server.py
If the server hangs, run from a terminal to see where it stops:
  cd kite_quant
  python -u app.py
Then open http://localhost:5000
"""
import sys
import os

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import app as app_module
        app_module.main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Failed to start: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
