# Favour AI

A cheerful birthday chatbot for Favour, built with Streamlit (recommended) and an optional FastAPI version.

## Project Structure

favour-ai/
  streamlit_app.py
  .streamlit/
    config.toml
  backend/
    main.py
  frontend/
    index.html
    style.css
    script.js
  .env
  .gitignore
  requirements.txt
  README.md

## Setup

1) Create and activate a virtual environment.

2) Install dependencies:

```
pip install -r requirements.txt
```

3) Add your Gemini API key in `.env` (local only):

```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

## Run (Streamlit)

Start the Streamlit app:

```
cd favour-ai
streamlit run streamlit_app.py
```

Open the app:
- Streamlit will print the local URL in the terminal (usually `http://localhost:8501`).

## Optional: Run FastAPI (legacy)

```
cd favour-ai
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/`.

## Deploy (Streamlit Community Cloud)

1) Push the repo to GitHub.
2) Create a new Streamlit app and select the GitHub repo.
3) Set the main file path to `streamlit_app.py`.
4) Add secrets:

```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

## Notes

- `.env` is excluded by `.gitignore` so secrets are not committed.
