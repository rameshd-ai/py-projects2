import json
from flask import Flask, render_template, request, redirect, url_for, session

# --- Flask Setup ---
app = Flask(__name__)
# IMPORTANT: Set a secret key for session management
app.secret_key = 'super_secret_key_for_session_management' 

# --- Flask Routes (Generic Form Wizard Demo) ---

@app.route('/', methods=['GET', 'POST'])
def form_wizard():
    """Handles the multi-step form logic, tracking state in the session."""
    
    # Initialize session state if not present
    if 'current_step' not in session:
        session['current_step'] = 1
        session['wizard_data'] = {}
        
    current_step = session['current_step']

    if request.method == 'POST':
        action = request.form.get('action')

        # Collect data from the current step's form fields before moving
        for key, value in request.form.items():
            if key not in ['action', 'csrf_token']: # Exclude control fields
                 # Handle checkboxes, which might be missing if unchecked
                 if key == 'newsletter':
                    session['wizard_data']['newsletter'] = 'on' if value == 'on' else 'off'
                 else:
                    session['wizard_data'][key] = value
        
        # Explicitly handle un-checked boxes for the current step (Step 2)
        if current_step == 2 and 'newsletter' not in request.form:
             session['wizard_data']['newsletter'] = 'off'


        if action == 'next' and current_step < 3:
            session['current_step'] += 1
            return redirect(url_for('form_wizard'))
        
        elif action == 'prev' and current_step > 1:
            session['current_step'] -= 1
            return redirect(url_for('form_wizard'))
            
        elif action == 'finish':
            # This is the final submit step. Clear session and show success.
            final_data = session['wizard_data']
            session.pop('current_step')
            session.pop('wizard_data')
            return render_template('index.html', step=4, final_data=final_data) # Step 4 is the success screen

    # If it's a GET request or a redirect, render the current step
    return render_template('index.html', 
                           step=current_step, 
                           data=session.get('wizard_data', {}))

if __name__ == '__main__':
    app.run(debug=True)