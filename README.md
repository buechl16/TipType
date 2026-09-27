# TipType

**For that word on the tip of your tongue.**

TipType is a context-aware vocabulary recommendation tool, for moments where you know exactly what you want to say, but can't find the exact word that fits. 
But Tiptype doesn't work as a normal thesaurus; instead, it looks at variables such as the surrounding sentence structure, selected writing mode, and various aspects of grammar to generate suggestions. 

To operate, users generate a sentence that contains a `____`, choose a writing mode, and will receive five ranked word recommendations, including locally calculated Fit Scores and short explanations/definitions!

TipType is **not** just an OpenAI wrapper. The Fit Score is calculated through Python, and is what determines what recommendations the user actually receives. 

## Features

- Three distinct writing modes: Creative, Academic, and Professional 
- Context-aware word generation using an LLM
- Custom TipType ranking system, with Fit Scores based on context, grammar, and writing style
- Click-to-insert recommendations
- Recommendation selection logging
- Local SQLite storage for recommendation data
- React + TypeScript frontend
- Python + FastAPI backend
- Error handling and input validation

## But How Does it Work?

TipType essentially separates the candidate *generation* from candidate *ranking*. 

The LLM generates eight possible words. Then, it independently estimates three scores for each candidate.

- **Context Score** — measures how well the word matches the intended meaning, surrounding context, and nuance of the given blank
- **Grammar Score** — how naturally the word's part of speech and grammatical form fit into the sentence
- **Style Score** — how well the word matches the selected writing mode

The current writing modes are:

- **Creative** — favors vivid, expressive, and distinctive wording
- **Academic** — favors precise, measured, and scholarly wording
- **Professional** — favors clear, polished, and workplace-appropriate wording

TipType then calculates its own Fit Score:

```text
Fit Score =
0.45 × Context Score
+ 0.30 × Style Score
+ 0.25 × Grammar Score
```

The language model does **not** choose the final ranking. Instead, TipType calculates the Fit Scores, sorts the candidates itself, and displays the five highest-scoring words.  This keeps candidate generation and ranking separate rather than simply displaying an ordered LLM response.

## Example

Input:

> The city had a ____ atmosphere that made folks uneasy.

Writing mode:

> Creative

Possible recommendations might include:

- eerie
- ominous
- haunting
- foreboding
- unsettling

Each recommendation includes a Fit Score and a short explanation of why the word fits the sentence and selected writing mode.

Once the recommendation are given, users can click a recommendation card to immediately insert that word into the original sentence.

## Behavioral Logging

Each recommendation request creates a unique session.

For every generated candidate, TipType stores:

- writing mode
- candidate word
- context score
- grammar score
- style score
- calculated Fit Score
- final rank
- whether the user selected the word

The user's original sentence is **never stored**.

When a user selects a recommendation, TipType only will record which candidate was accepted for that session.
This behavioral data can later be used to evaluate recommendation quality and experiment with personalized ranking.

For example, future versions/updates aim to measure things like:

- Top-1 acceptance rate
- Top-3 acceptance rate
- average selected rank
- performance by writing mode
- whether personalized ranking improves over generic ranking

## Tech Stack

### Frontend

- React
- TypeScript
- Vite
- CSS

### Backend

- Python
- FastAPI
- Pydantic

### AI

- OpenAI API
- Structured model outputs

### Data

- SQLite

## Project Structure

```text
TipType/
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── llm.py
│   ├── ranking.py
│   ├── database.py
│   ├── requirements.txt
│   └── tests
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   └── styles.css
│   ├── package.json
│   └── index.html
│
├── .gitignore
└── README.md
```

## Running TipType Locally

### Requirements

- Python 3.10+
- Node.js
- OpenAI API key

### Backend

From the project directory:

```sh
cd backend

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements.txt
cp .env.example .env
```

Add your OpenAI API key to `backend/.env`:

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

The `.env` file is ignored by Git so the API key is not committed to the repository.

Start the FastAPI backend:

```sh
python -m uvicorn main:app --reload --host localhost --port 8000
```

### Frontend

Open another terminal and run:

```sh
cd frontend
npm install
npm run dev
```

Then open:

```text
http://localhost:5173
```

Both the frontend and backend need to be running for TipType to generate recommendations.

## Testing

Backend tests can be run without making paid OpenAI API calls:

```sh
cd backend
source .venv/bin/activate
python -m unittest -v
```

The backend tests cover areas including:

- ranking calculations
- score rounding
- candidate validation
- input validation
- API error handling
- behavioral logging
- recommendation selection updates
- database behavior

The frontend production build can be checked with:

```sh
cd frontend
npm run build
```

## Current Scope

TipType is currently an prototype focused on one core problem:

> **I know what I mean. Help me find the word that belongs here.**

At the moment, it's not designed to generate full essays or act as a general-purpose AI writing assistant.

What the current version does focus on is:

1. generating context-aware vocabulary candidates
2. evaluating candidates using several features
3. ranking those candidates through TipType's own scoring system
4. allowing users to select and insert a recommendation
5. collecting behavioral data that can support future evaluation and personalization

## Future Work

The current version is just the first stage of the larger TipType idea.

Future features I would like to explore include:

- **Voice Context profiles** that describe how a particular character, author, paper, or project should sound
- **Personal Voice profiles** that learn which types of vocabulary a user tends to prefer
- project-specific writing styles and vocabulary preferences
- recommendation analytics dashboards
- Top-1 and Top-3 acceptance metrics
- average selected-rank analysis
- score calibration analysis
- personalized vocabulary recommendations
- manuscript and document context using embeddings and retrieval
- vector-based context search for larger writing projects
- comparison of generic and personalized recommendation ranking
- learned reranking using behavioral data
- experiments comparing LLM order, rule-based ranking, and learned ranking

Eventually, the manually designed ranking system could act as a baseline for a learned model. For example, recommendation interactions could be treated as training data using features such as context/style relevance, word frequency, grammar fit, semantic similarity, historical acceptance, etc. A future model could then learn which candidates users are most likely to select and use that information to personalize the final ranking.

The long-term goal is for TipType to understand not only:

> **Which word fits this sentence?**

but also:

> **Which word fits this sentence, while still sounding like the person writing it?**

## Feedback...
Please enjoy, and feel free to share any suggestions, ideas, or feedback my way! I'm always looking for ways to improve TipType. 
