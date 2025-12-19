import os
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError 
import pandas as pd 
from urllib.parse import urlparse 
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import os.path # Import os.path for safe path joining

# --- Placeholder for Helper Functions (Assuming you have a correct helper.py) ---
try:
    from helper import (
        login_token_generator,
        payload_mapper,
        payload_creator,
        add_menu_data,
        load_settings,
        download_and_save_menu_data,
        preprocess_menu_data
    )
except ImportError:
    # Dummy implementation for missing helper functions
    def login_token_generator(): return "dummy_token"
    def payload_mapper(): return {}
    def payload_creator(): return {}
    def add_menu_data(data): print(f"Adding menu data: {data}")
    def load_settings(): return {"source_site_url": "example.com", "destination_site_url": "test.com"}
    def download_and_save_menu_data(): print("Downloading menu data...")
    def preprocess_menu_data(payload, token): print(f"Preprocessing with token: {token}")
    print("WARNING: Using dummy helper functions. Ensure 'helper.py' exists and is correct.")
# ------------------------------------------------------------------------


app = Flask(__name__)
app.secret_key = "supersecretkey"

SETTINGS_FILE = "input/settings.json"

# --- FOLDER CONFIGURATION ---
UPLOAD_FOLDER = 'uploads'
FAQ_OUTPUT_FOLDER = 'faq-output' 

os.makedirs('input', exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FAQ_OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['FAQ_OUTPUT_FOLDER'] = FAQ_OUTPUT_FOLDER 

# --- GLOBAL STATE ---
uploaded_files_data = [] 


# --- INITIALIZE FILE LISTS ---
def scan_existing_files():
    global uploaded_files_data 

    uploaded_files_data.clear()
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(file_path) and not filename.startswith('.'):
            uploaded_files_data.append({
                'name': filename,
                'path': file_path,
                'size': os.path.getsize(file_path) / (1024 * 1024),
                'date_time': time.ctime(os.path.getmtime(file_path))
            })

    uploaded_files_data.sort(key=lambda x: x['date_time'], reverse=True)


scan_existing_files()


# --- SAVE SETTINGS ---
def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=4)
        return True
    except IOError as e:
        print(f"Error saving settings file: {e}")
        return False


# --- ROUTES ---

@app.route("/", methods=["GET", "POST"])
def settings():
    data = load_settings()
    if request.method == "POST":
        form_data = {
            "source_site_id": request.form.get("source_site_id"),
            "source_site_url": request.form.get("source_site_url"),
            "source_profile_alias": request.form.get("source_profile_alias"),
            "destination_site_id": request.form.get("destination_site_id"),
            "destination_site_url": request.form.get("destination_site_url"),
            "destination_profile_alias": request.form.get("destination_profile_alias"),
        }
        if save_settings(form_data):
            flash("Settings saved successfully!", "success")
        else:
            flash("Error: Could not save settings.", "danger")
        return redirect(url_for("settings"))
    return render_template("settings.html", data=data)


@app.route("/move_menu", methods=["GET", "POST"])
def move_menu():
    settings_data = load_settings()
    if request.method == "POST":
        try:
            token = login_token_generator()
            download_and_save_menu_data()
            time.sleep(1)
            mapped_payload = payload_mapper()
            time.sleep(1)
            final_payload = payload_creator()
            time.sleep(1)
            preprocess_menu_data(final_payload, token)
            flash("Move process completed successfully!", "info")
        except Exception as e:
            flash(f"Move process failed: {e}", "danger")
    return render_template("move_menu.html", settings=settings_data)


@app.route('/faq', methods=['GET', 'POST'])
def faq():
    global uploaded_files_data
    if request.method == 'POST':
        if 'excelFile' not in request.files:
            flash('No file part', 'danger')
            return redirect(url_for('faq'))

        file = request.files['excelFile']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(url_for('faq'))

        if file:
            filename = secure_filename(file.filename)
            name, ext = os.path.splitext(filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            counter = 1
            while os.path.exists(file_path):
                filename = f"{name}_{counter}{ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                counter += 1

            file.save(file_path)
            # Re-scan to update the global list accurately
            scan_existing_files()
            
            flash(f'File "{filename}" uploaded successfully! Click Process to begin extraction.', 'success')
            return redirect(url_for('faq'))

    # Prepare output files list for the template
    output_files = os.listdir(app.config['FAQ_OUTPUT_FOLDER'])
    output_files_info = []
    for filename in output_files:
        file_path = os.path.join(app.config['FAQ_OUTPUT_FOLDER'], filename)
        if os.path.isfile(file_path) and not filename.startswith('.'):
            output_files_info.append({
                'name': filename,
                'size': os.path.getsize(file_path) / (1024 * 1024),
                'date_time': time.ctime(os.path.getmtime(file_path))
            })
            
    return render_template('faq.html',
                           active_page='faq',
                           uploaded_files=uploaded_files_data,
                           output_files=output_files_info)


# New Route to Handle File Deletion (for both uploads and output)
@app.route('/api/delete_file/<folder>/<filename>', methods=['DELETE'])
def api_delete_file(folder, filename):
    safe_filename = secure_filename(filename)
    
    if folder == 'uploads':
        target_folder = app.config['UPLOAD_FOLDER']
        # Re-scan local list immediately after deletion
        global uploaded_files_data
        
    elif folder == 'output':
        target_folder = app.config['FAQ_OUTPUT_FOLDER']
    else:
        return json.dumps({'success': False, 'error': 'Invalid folder specified.'}), 400

    file_path = os.path.join(target_folder, safe_filename)

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # Update global state for uploaded files if necessary
            if folder == 'uploads':
                scan_existing_files()
                
            return json.dumps({'success': True, 'message': f'File {safe_filename} deleted.'}), 200
        else:
            return json.dumps({'success': False, 'error': 'File not found.'}), 404
    except Exception as e:
        print(f"Error deleting file {file_path}: {e}")
        return json.dumps({'success': False, 'error': f'Failed to delete file: {e}'}), 500


# Route to Handle Downloads
@app.route('/downloads/<filename>')
def download_file(filename):
    """Serves the generated files from the faq-output folder."""
    return send_from_directory(app.config['FAQ_OUTPUT_FOLDER'], filename, as_attachment=True)


# ... (api_preview and api_process_file remain the same as the previous correct version)
# ... (Only including api_process_file here for completeness, as it is critical)

@app.route('/api/process_file/<filename>', methods=['POST'])
def api_process_file(filename):
    """
    Reads the uploaded file, extracts source links, HITS EACH API URL USING A HEADLESS BROWSER 
    (Playwright) to bypass bot detection, aggregates the data with a Source_URL column, 
    and saves it to a single Excel file with Source_URL as the first column.
    """
    try:
        file_info = next((item for item in uploaded_files_data if item['name'] == filename), None)
        if not file_info:
            return json.dumps({'success': False, 'error': 'File not found'}), 404

        file_path = file_info['path']
        safe_filename = file_info['name']
        
        if safe_filename.endswith(('.csv', '.txt')):
            df_uploaded = pd.read_csv(file_path, encoding='utf-8')
        elif safe_filename.endswith(('.xlsx', '.xls')):
            df_uploaded = pd.read_excel(file_path)
        else:
            return json.dumps({'success': False, 'error': 'Unsupported file type'}), 400

        if df_uploaded.empty:
            return json.dumps({'success': False, 'error': 'Input file is empty, no links processed.'}), 200

        first_column_name = df_uploaded.columns[0]
        source_links = df_uploaded[first_column_name].dropna().astype(str).tolist()

        print(f"\n🧩 --- Starting API Processing for {filename} using Playwright (Headless) ---")
        
        all_faq_data = [] 
        processed_count = 0
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True) 
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
            )
            
            context.set_default_timeout(30000) # 30 seconds timeout
            page = context.new_page()

            for i, link in enumerate(source_links):
                link = link.strip()
                if not link.startswith(('http://', 'https://')):
                    link = 'https://' + link 
                
                try:
                    parsed_url = urlparse(link)
                    if not parsed_url.netloc:
                        print(f"Skipping invalid URL: {link}")
                        continue
                    
                    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}".rstrip('/')
                    faq_api_url = f"{base_url}/api/FAQApi/GetFAQList"
                    
                    print(f"  -> Intercepting network request for URL {i+1}: {faq_api_url}")

                    json_data = None
                    
                    def handle_api_response(response):
                        nonlocal json_data
                        if response.url == faq_api_url and response.status == 200:
                            try:
                                json_data = response.json()
                            except Exception:
                                pass

                    page.on("response", handle_api_response)
                    
                    page.goto(faq_api_url, wait_until="networkidle") 
                    time.sleep(2) # Give a moment for the handler to fire

                    if not json_data:
                        raw_content = page.evaluate('document.body.textContent')
                        try:
                            json_data = json.loads(raw_content)
                        except json.JSONDecodeError:
                            print(f"  -> ERROR: Failed to parse raw page content as JSON for {faq_api_url}. Challenge failed.")
                            continue

                    if not isinstance(json_data, list) or not json_data:
                        print(f"  -> WARN: API returned empty or unexpected data for {faq_api_url}. Skipping.")
                        continue
                    
                    df_output = pd.DataFrame(json_data)
                    df_output['Source_URL'] = faq_api_url
                    
                    all_faq_data.append(df_output)
                    processed_count += 1
                    
                    print(f"  -> SUCCESS: Fetched {len(json_data)} FAQs from {faq_api_url}")

                except PlaywrightTimeoutError:
                    print(f"  -> ERROR: Playwright Timeout while loading or waiting for response for {faq_api_url}. Challenge likely failed.")
                except Exception as e:
                    print(f"  -> ERROR: Failed to process data/run Playwright for {faq_api_url}: {e}")
                    continue
            
            browser.close()

        if not all_faq_data:
            return json.dumps({'success': False, 'error': 'No data was successfully fetched from any API link.'}), 200

        final_df = pd.concat(all_faq_data, ignore_index=True)

        # COLUMN REORDERING LOGIC: Moves 'Source_URL' to the front
        current_columns = final_df.columns.tolist()
        if 'Source_URL' in current_columns:
            current_columns.remove('Source_URL')
            new_column_order = ['Source_URL'] + current_columns
            final_df = final_df[new_column_order]

        name, _ = os.path.splitext(safe_filename)
        output_name = f"{name}.xlsx"
        output_path = os.path.join(app.config['FAQ_OUTPUT_FOLDER'], output_name)
        
        final_df.to_excel(output_path, index=False)
        
        print(f"Completed processing. Saved aggregated data ({len(final_df)} rows) to '{output_name}' in 'faq-output'.")

        return json.dumps({'success': True, 'processed_count': processed_count, 'output_file': output_name}), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        print(f"🔥 Unexpected Global Error during processing {filename}: {e}")
        return json.dumps({'success': False, 'error': f"Unexpected Error: {e}"}), 500


if __name__ == "__main__":
    app.run(debug=True)