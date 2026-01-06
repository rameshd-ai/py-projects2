# Figma to CMS Component Generator

A Flask application that converts Figma designs to CMS components using LangGraph, PostgreSQL + pgvector, and Claude AI.

## 🎯 Overview

This tool automates the conversion of Figma designs into CMS-ready components by:
1. Downloading screenshots from Figma
2. Using AI to generate HTML from designs
3. Matching similar components using vector search
4. Generating CMS-compatible JSON files (Config, Format, Records)

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL with pgvector extension
- Figma API access token
- CMS API credentials
- Claude AI API key

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd finalDtoC
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and credentials
```

5. Set up PostgreSQL database:
```sql
CREATE DATABASE miblock_components;
\c miblock_components
CREATE EXTENSION vector;
```

6. Run the Flask app:
```bash
python app.py
```

7. Open your browser to `http://localhost:5000`

## 📁 Project Structure

```
finalDtoC/
├── app.py                 # Flask application
├── agents/               # LangGraph workflow (Phase 2)
├── api/                  # API clients (Figma, CMS, Claude)
├── models/               # Database models (Phase 3)
├── utils/                # Utilities (matching, generation)
├── templates/            # HTML templates
├── static/               # CSS and static files
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🗺️ Development Phases

### Phase 1: Basic Flask App + API Clients ✅
- Flask app setup
- Figma API client
- CMS API client
- Claude AI client

### Phase 2: LangGraph Workflow (In Progress)
- Agent workflow implementation
- Component matching logic
- HTML generation pipeline

### Phase 3: Component Matching
- PostgreSQL + pgvector setup
- Vector similarity search
- Component library refresh

### Phase 4: JSON Generation & Polish
- CMS JSON file generation
- UI improvements
- Download functionality

## 🔧 Configuration

Edit `.env` file with your credentials:

- `FIGMA_ACCESS_TOKEN`: Your Figma personal access token
- `CMS_BASE_URL`: Your CMS API base URL
- `CMS_API_KEY`: Your CMS API key
- `ANTHROPIC_API_KEY`: Your Claude AI API key
- `DATABASE_URL`: PostgreSQL connection string

## 📝 Usage

1. Enter a Figma URL in the web interface
2. Click "Generate Component"
3. The system will:
   - Download the screenshot from Figma
   - Generate HTML using Claude AI
   - Match against existing components (if available)
   - Generate CMS JSON files
4. Download the generated files

## 🛠️ Technology Stack

- **Flask**: Web framework
- **LangGraph**: Agent orchestration
- **PostgreSQL + pgvector**: Vector database for component matching
- **Claude AI**: HTML generation from screenshots
- **CLIP**: Visual embeddings for similarity search

## 📄 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines here]


