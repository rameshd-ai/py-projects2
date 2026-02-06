"""
Automated Zerodha Access Token Generator
Runs a local Flask server to handle OAuth callback and generate access token automatically.
"""
import json
import sys
import webbrowser
from pathlib import Path
from threading import Timer

try:
    from kiteconnect import KiteConnect
    from flask import Flask, request, redirect
except ImportError as e:
    print(f"[ERROR] Required library not installed: {e}")
    print("Install with: pip install kiteconnect flask")
    sys.exit(1)


def load_config():
    """Load config.json"""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, 'r') as f:
        return json.load(f)


def save_access_token(access_token: str):
    """Save access token to config.json"""
    config_path = Path(__file__).parent / "config.json"
    config = load_config()
    config["ZERODHA_ACCESS_TOKEN"] = access_token
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    return config_path


# Global variables
kite = None
api_secret = None
access_token_generated = None

# Create Flask app
app = Flask(__name__)


@app.route('/')
def callback():
    """Handle OAuth callback from Zerodha"""
    global access_token_generated
    
    request_token = request.args.get('request_token')
    status = request.args.get('status')
    
    if status != 'success' or not request_token:
        return f"""
        <html>
        <head><title>Error</title></head>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1 style="color: #e74c3c;">❌ Authorization Failed</h1>
            <p>Status: {status}</p>
            <p>Please try again.</p>
            <script>setTimeout(function(){{ window.close(); }}, 3000);</script>
        </body>
        </html>
        """
    
    try:
        # Generate session and get access token
        print(f"\n[INFO] Received request token: {request_token[:10]}...")
        print("[INFO] Generating access token...")
        
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        access_token_generated = access_token
        
        # Save to config
        config_path = save_access_token(access_token)
        
        print(f"\n[SUCCESS] Access token generated!")
        print(f"[SUCCESS] Saved to: {config_path}")
        print(f"\nAccess Token: {access_token}\n")
        
        # Schedule shutdown
        Timer(2.0, lambda: shutdown_server()).start()
        
        return f"""
        <html>
        <head><title>Success</title></head>
        <body style="font-family: Arial; padding: 40px; text-align: center; background: #f0f0f0;">
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto;">
                <h1 style="color: #27ae60;">✅ Success!</h1>
                <h3>Access Token Generated</h3>
                <div style="background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; word-break: break-all;">
                    <code style="color: #333;">{access_token}</code>
                </div>
                <p style="color: #666;">Token has been saved to config.json</p>
                <p style="color: #999; font-size: 14px;">This window will close automatically...</p>
            </div>
            <script>setTimeout(function(){{ window.close(); }}, 3000);</script>
        </body>
        </html>
        """
    except Exception as e:
        print(f"\n[ERROR] Failed to generate access token: {e}")
        return f"""
        <html>
        <head><title>Error</title></head>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1 style="color: #e74c3c;">❌ Error</h1>
            <p>{str(e)}</p>
            <script>setTimeout(function(){{ window.close(); }}, 5000);</script>
        </body>
        </html>
        """


def shutdown_server():
    """Shutdown the Flask server"""
    print("\n[INFO] Shutting down server...")
    sys.exit(0)


def main():
    """Main function to start OAuth flow"""
    global kite, api_secret
    
    print("\n" + "="*60)
    print("ZERODHA AUTOMATED TOKEN GENERATOR")
    print("="*60)
    
    # Load config
    print("\n[INFO] Loading configuration...")
    config = load_config()
    
    api_key = config.get("ZERODHA_API_KEY")
    api_secret = config.get("ZERODHA_API_SECRET")
    
    if not api_key or not api_secret:
        print("[ERROR] API Key or Secret not found in config.json")
        sys.exit(1)
    
    print(f"[INFO] API Key: {api_key}")
    print(f"[INFO] API Secret: {api_secret[:10]}...")
    
    # Initialize Kite Connect
    kite = KiteConnect(api_key=api_key)
    
    # Get login URL
    login_url = kite.login_url()
    
    print("\n" + "="*60)
    print("STEP 1: Opening Zerodha Login in Browser")
    print("="*60)
    print("\n[INFO] A browser window will open automatically")
    print("[INFO] Please login with your Zerodha credentials")
    print("[INFO] After authorization, you'll be redirected back")
    print("\n[INFO] Starting local server on http://127.0.0.1:5000")
    print("[INFO] Waiting for authorization...")
    print("\n" + "="*60)
    
    # Open browser automatically
    Timer(1.0, lambda: webbrowser.open(login_url)).start()
    
    # Start Flask server
    try:
        app.run(host='127.0.0.1', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n\n[INFO] Process interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Server error: {e}")


if __name__ == "__main__":
    main()
