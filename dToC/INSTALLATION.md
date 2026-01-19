# Installation Guide

Simple setup instructions for developers.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## Quick Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd dToC
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   - Open your browser and go to: `http://127.0.0.1:5000/`

## Project Structure

- `app.py` - Main Flask application
- `config.py` - Configuration and processing steps
- `processing_steps/` - Processing logic modules
- `templates/` - HTML templates
- `uploads/` - Uploaded files directory (auto-created)
- `output/` - Generated output files (auto-created)

## Notes

- The application will automatically create `uploads/` and `output/` directories if they don't exist
- Default port is 5000 (change in `app.py` if needed)
- Upload file size limit: 16MB (configured in `config.py`)
