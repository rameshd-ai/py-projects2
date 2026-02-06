"""
Test Zerodha Kite Connect API connection and generate access token.
Run this script to authenticate and get your access token.
"""
import json
import sys
from pathlib import Path

try:
    from kiteconnect import KiteConnect
except ImportError:
    print("[ERROR] KiteConnect library not installed!")
    print("Install it with: pip install kiteconnect")
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
    print(f"✅ Access token saved to config.json")


def generate_access_token():
    """Generate access token through Kite Connect login flow"""
    config = load_config()
    api_key = config.get("ZERODHA_API_KEY")
    api_secret = config.get("ZERODHA_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ API Key or Secret not found in config.json")
        return None
    
    print(f"🔑 API Key: {api_key}")
    print(f"🔒 API Secret: {api_secret[:10]}...")
    
    kite = KiteConnect(api_key=api_key)
    
    # Step 1: Get login URL
    login_url = kite.login_url()
    print("\n" + "="*60)
    print("📋 STEP 1: Login to Zerodha")
    print("="*60)
    print(f"\n🌐 Open this URL in your browser:\n\n{login_url}\n")
    print("1. Login with your Zerodha credentials")
    print("2. Authorize the app")
    print("3. You'll be redirected to a URL")
    print("4. Copy the 'request_token' from the redirected URL")
    print("\nExample URL after redirect:")
    print("http://127.0.0.1/?request_token=ABC123&action=login&status=success")
    print("                              ^^^^^^^ Copy this part")
    print("\n" + "="*60)
    
    # Step 2: Get request token from user
    request_token = input("\n📝 Paste the request_token here: ").strip()
    
    if not request_token:
        print("❌ No request token provided!")
        return None
    
    try:
        # Step 3: Generate session (access token)
        print("\n🔄 Generating access token...")
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        
        print("\n" + "="*60)
        print("✅ SUCCESS! Access token generated")
        print("="*60)
        print(f"\n🎫 Access Token: {access_token}\n")
        
        # Save to config
        save_access_token(access_token)
        
        return access_token
    except Exception as e:
        print(f"\n❌ Error generating access token: {e}")
        return None


def test_connection(access_token: str = None):
    """Test Zerodha API connection"""
    config = load_config()
    api_key = config.get("ZERODHA_API_KEY")
    
    if not access_token:
        access_token = config.get("ZERODHA_ACCESS_TOKEN")
    
    if not api_key or not access_token:
        print("❌ API Key or Access Token missing!")
        return False
    
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        print("\n" + "="*60)
        print("🧪 Testing API Connection")
        print("="*60)
        
        # Test 1: Get profile
        print("\n1️⃣ Fetching profile...")
        profile = kite.profile()
        print(f"   ✅ User: {profile.get('user_name')} ({profile.get('email')})")
        print(f"   📧 Broker: {profile.get('broker', 'Zerodha')}")
        
        # Test 2: Get margins
        print("\n2️⃣ Fetching margins...")
        margins = kite.margins()
        equity_margin = margins.get('equity', {})
        available = equity_margin.get('available', {}).get('live_balance', 0)
        print(f"   ✅ Available Balance: ₹{available:,.2f}")
        
        # Test 3: Get positions
        print("\n3️⃣ Fetching positions...")
        positions = kite.positions()
        net_positions = positions.get('net', [])
        open_positions = [p for p in net_positions if int(p.get('quantity', 0)) != 0]
        print(f"   ✅ Open Positions: {len(open_positions)}")
        
        # Test 4: Get quote for NIFTY 50
        print("\n4️⃣ Fetching Nifty 50 quote...")
        quote = kite.quote("NSE:NIFTY 50")
        nifty_data = quote.get("NSE:NIFTY 50", {})
        last_price = nifty_data.get("last_price", 0)
        print(f"   ✅ Nifty 50: ₹{last_price:,.2f}")
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED! Zerodha API is working!")
        print("="*60)
        return True
        
    except Exception as e:
        print(f"\n❌ Connection test failed: {e}")
        print("\nPossible issues:")
        print("1. Access token expired (regenerate daily)")
        print("2. API key/secret incorrect")
        print("3. Network/firewall issues")
        return False


def main():
    """Main function"""
    config = load_config()
    access_token = config.get("ZERODHA_ACCESS_TOKEN")
    
    print("\n" + "="*60)
    print("🔧 ZERODHA KITE CONNECT - CONNECTION TEST")
    print("="*60)
    
    if not access_token:
        print("\n⚠️  No access token found!")
        print("Let's generate one...\n")
        access_token = generate_access_token()
        
        if not access_token:
            print("\n❌ Failed to generate access token")
            sys.exit(1)
    else:
        print(f"\n✅ Access token found in config")
        print("Testing connection...\n")
    
    # Test connection
    success = test_connection(access_token)
    
    if not success:
        print("\n⚠️  Connection test failed!")
        print("\nDo you want to regenerate the access token? (y/n): ", end="")
        choice = input().strip().lower()
        if choice == 'y':
            access_token = generate_access_token()
            if access_token:
                test_connection(access_token)


if __name__ == "__main__":
    main()
