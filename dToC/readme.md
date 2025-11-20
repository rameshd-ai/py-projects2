# Real-Time XML Processing Pipeline (Flask + SSE)

This project demonstrates a robust pipeline for processing XML files in a web environment using **Flask** and **Server-Sent Events (SSE)**. The SSE architecture allows long-running, multi-step processing jobs to provide users with real-time feedback on their progress directly in the browser.

## ✨ Features

* **Real-Time Progress:** Uses **Server-Sent Events (SSE)** for instant, per-step updates in the browser.
* **Modular Pipeline:** Processing logic is broken down into interchangeable steps defined in `config.py`.
* **Dynamic Execution:** Steps are dynamically loaded and executed sequentially by the `utils.py` orchestration layer.
* **File Cleanup:** Automatically deletes the uploaded source file upon completion or error.
* **Isolated Logic:** Business logic (XML parsing, cleaning, JSON generation) is separated into the `processing_steps` module, making the core application clean and scalable.

---

## 💻 Project File Structure

| File Name | Role & Responsibility |
| :--- | :--- |
| **`app.py`** | The main Flask application entry point. Handles web requests, file uploads, and routing (`/`, `/upload`, `/stream`). |
| **`config.py`** | **Central configuration and pipeline definition.** Defines global constants and the execution order (`PROCESSING_STEPS`). |
| **`utils.py`** | **Processing orchestration and SSE handler.** Dynamically loads, runs steps, manages errors, and streams progress to the client. |
| **`index.html`** | The user interface (UI). Contains the upload form and JavaScript for connecting to the SSE stream. |
| **`processing_steps/`** | Directory containing the specialized business logic for each stage. |
| ├── **`process_xml.py`** | Core function (`run_xml_processing_step`) for reading XML, cleaning data, and generating JSON files. |
| └── **`cleanup.py`** | Finalization step (`run_cleanup_step`) that confirms pipeline completion and prepares for final actions. |

---

## 🚀 Getting Started

### Prerequisites

* Python 3.8+
* `pip` (Python package installer)

### Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone [YOUR_REPO_URL]
    cd [YOUR_PROJECT_NAME]
    ```

2.  **Create a virtual environment and activate it:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install Flask
    ```

4.  **Ensure required directories exist:**
    ```bash
    mkdir uploads
    mkdir processing_steps
    ```
    *(Place the Python step files within the `processing_steps` directory.)*

### Running the Application

1.  **Start the Flask server:**
    ```bash
    python app.py
    ```

2.  **Access the application:**
    Open your browser and navigate to `http://127.0.0.1:5000/`.

---

## ⚙️ Pipeline Configuration

The processing workflow is defined in the `config.py` file under the `PROCESSING_STEPS` list. **The connection between the file system and the code is managed by the `id` and `module` keys.**

| Key | Description |
| :--- | :--- |
| **`id`** | **(Crucial)** Must match the filename (e.g., `"cleanup"` matches `cleanup.py`). Used by `utils.py` to import the module. |
| **`name`** | The friendly name displayed in the UI progress list. |
| **`module`** | **(Crucial)** Must match the name of the function inside the module file that executes the step (e.g., `"run_cleanup_step"`). |
| **`delay`** | (Optional) A time delay in seconds, often used for debugging or simulating job duration. |

### Example Step Configuration (`config.py`)

```python
PROCESSING_STEPS = [
    {
        "id": "process_xml", 
        "name": "Processing XML and Generating JSON Structures", 
        "module": "run_xml_processing_step", 
        "delay": 2.5, 
        "error_chance": 0.00
    },
    # ...
]