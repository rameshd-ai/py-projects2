import os
import json
from flask import Flask, request, render_template

# Import the API logic from the separate file
from figma_api import parse_figma_url, fetch_figma_data

# --- FLASK APP SETUP ---
app = Flask(__name__)
# Add a simple secret key for basic security best practice
app.config['SECRET_KEY'] = os.urandom(24) 

# --- FLASK ROUTES ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main route handling the form submission and data display."""
    
    results = None
    file_key = None
    node_id = None
    
    # Get form data
    token = request.form.get('token', '')
    url = request.form.get('url', '')
    
    if request.method == 'POST' and token and url:
        # Use the helper to parse the URL
        file_key, node_id = parse_figma_url(url)

        if not file_key:
            results = {'error': "Could not extract File Key from the provided URL."}
        else:
            # Use the API function to fetch data
            results = fetch_figma_data(token, file_key, node_id)
            results['file_key'] = file_key
            results['node_id'] = node_id if node_id else "N/A"
            
    # Render the template, passing results and default form values
    return render_template('index.html', 
                           results=results, 
                           default_token=token, 
                           default_url=url)

# --- RUN APP ---

if __name__ == '__main__':
    # Flask runs on 127.0.0.1:5000 by default
    print("Flask app is starting. Navigate to http://127.0.0.1:5000/")
    # Note: Ensure all dependencies (Flask, requests) are installed
    app.run(debug=True)
