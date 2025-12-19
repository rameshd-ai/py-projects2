import os
import json
import time
import requests
from flask import Flask, render_template, request, redirect, url_for, flash
from helper import login_token_generator,payload_mapper,payload_creator,add_menu_data,load_settings,download_and_save_menu_data,preprocess_menu_data

app = Flask(__name__)
app.secret_key = "supersecretkey"

SETTINGS_FILE = "input/settings.json"



# Save settings to JSON
def save_settings(data):
    """Saves settings data to the settings.json file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=4)
        return True
    except IOError as e:
        print(f"Error saving settings file: {e}")
        return False

# Route for the Settings page
@app.route("/", methods=["GET", "POST"])
def settings():
    """
    Handles the display and saving of site configuration settings.
    """
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

# Route for the "Move Menu" page
@app.route("/move_menu", methods=["GET", "POST"])
def move_menu():
    """
    Handles the "Move Menu" functionality.
    The "move" logic now runs only on a POST request.
    """
    settings_data = load_settings()
    menu_data = None
    
    # This block now correctly executes ONLY on a POST request.
    if request.method == "POST":
        # Step 1: Get login token
        token = None
        token = login_token_generator()

        # # Step 2: Download payload
        menu_download = download_and_save_menu_data()
        time.sleep(2)
        # # Step 3: Map payload
        mapped_payload = payload_mapper()       
        time.sleep(2)
        # Step 4: Create payload
        final_payload = payload_creator()
        time.sleep(2)
        # Step 5: Add menu data
        result = preprocess_menu_data(final_payload, token)
        # result = add_menu_data()
        

        # flash(f"Move process completed. Result: {result}", "info")
        
        # To show a result in the table, you must provide data here.
        # This is a static example of the results.
        menu_data = None

    # The render_template call remains outside the if block to ensure the page always loads
    return render_template("move_menu.html", settings=settings_data, menu_data=menu_data)


@app.route('/faq')
def faq():
    return render_template('faq.html', active_page='faq')

@app.route('/upload_data', methods=['POST'])
def upload_data():
    if 'excelFile' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('faq'))

    file = request.files['excelFile']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('faq'))

    if file:
        try:
            # Read file directly into pandas DataFrame
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            # ... Process df here ...
            flash('File processed successfully!', 'success')
        except Exception as e:
            flash(f'Error processing file: {e}', 'danger')

    return redirect(url_for('faq'))


if __name__ == "__main__":
    app.run(debug=True)