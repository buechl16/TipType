import { useState, type FormEvent } from 'react';

// writing modes the user chooses from
const modes = ['Creative', 'Academic', 'Professional'] as const;
type Mode = (typeof modes)[number];

// shape of reccomendation returned by backend
type Recommendation = {
  word: string;
  fit_score: number;
  explanation: string;
};

export default function App() {
    // frontend state
    // what the user is currently typing
  const [sentence, setSentence] = useState('People had mixed ____ on the concept.');
    //current writing mode
  const [mode, setMode] = useState<Mode>('Creative');
    //recc cards
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
    // saves the og sentence containing ___
    // this lets user select and explore diff reccomendation cards w/o losing blank
  const [recommendationSentence, setRecommendationSentence] = useState('');
    // tracks which recc user selected
  const [selectedWord, setSelectedWord] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [isSavingSelection, setIsSavingSelection] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  function clearRecommendations() {
    setRecommendations([]);
    setSelectedWord('');
    setSessionId('');
  }

  async function insertWord(word: string) {
    // if no active session or selection being saved no nothing
      if (!sessionId || isSavingSelection) return;
    setIsSavingSelection(true);
    setError('');
    try {
        // tells backend which recc the user chose!
      const response = await fetch(`http://localhost:8000/sessions/${sessionId}/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word }),});
      if (!response.ok) {
        throw new Error('Could not save your selection. Re-click the card to try again!');
      }
      // replace ____ w/selected word
        // only after the backend confirms the selection.
      setSentence(recommendationSentence.replace('____', () => word));
      setSelectedWord(word);
    } catch {
      setError('Could not save your selection. Re-click click the card to try again.');
    } finally {
      setIsSavingSelection(false);
    }
  }

  // -----------------------------
// Request recommendations
// -----------------------------

async function findWords(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  // clears old messages/results before starting a new request.
  setError('');
  setRecommendations([]);
  setSelectedWord('');
  setSessionId('');

  // user included a ____ before sending anything to backend
  if (!sentence.includes('____')) {
    setError('Include ____ (four underscores) where your word should go.');
    return;
  }

  setIsLoading(true);

  try {
    // send the sentence and selected writing mode to the FastAPI.
    const response = await fetch('http://localhost:8000/recommend', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        sentence,
        mode,
      }),
    });

    // If FastAPI returns an error, turn it into a error message on frontend
    if (!response.ok) {
      const problem = await response.json();
      if (typeof problem.detail === 'string') {
        throw new Error(problem.detail);}
      throw new Error(`The server could not complete the request (${response.status}).`,);}

    // reads the successful response from fastAPI.
    const data: {session_id: string; recommendations: Recommendation[]; } = await response.json();

    // Save the session and recommendations in React state.
    setSessionId(data.session_id);
    setRecommendationSentence(sentence);
    setRecommendations(data.recommendations);

  } catch (error) {
    if (error instanceof TypeError) {
      setError(
        'Could not reach the backend. Make sure FastAPI is running on http://localhost:8000.',
      );
    } else if (error instanceof Error) {
      setError(error.message);
    } else {
      setError('Something went wrong. Please try again.');
    }

  } finally {
      // stops loading state
    setIsLoading(false);
  }
}

  return (
  <>
    <nav className="navbar" aria-label="Main navigation">
      <div className="nav-inner">
        <p className="brand">TipType</p>
        <div className="nav-links">
          <span>About</span>
          <span>How It Works</span>
          <span>GitHub</span>
        </div>
      </div>
    </nav>

    <main>
      <header className="hero">
        <h1>For that word on the tip of your tongue.</h1>
        <p className="intro">
          Leave a blank, choose your tone, and explore possibilities.
        </p>
      </header>

      <form onSubmit={findWords}>
        <label htmlFor="sentence">Add your sentence.</label>
        <p id="sentence-help" className="hint">
          Use ____ (four underscores) for the missing word.
        </p>

        <textarea
          id="sentence"
          aria-describedby="sentence-help"
          value={sentence}
          onChange={(event) => {
            setSentence(event.target.value);
            clearRecommendations();
          }}
          placeholder="People had mixed ____ on the concept."
          rows={4}
          required
          disabled={isLoading || isSavingSelection}
        />

        <fieldset disabled={isLoading || isSavingSelection}>
          <legend>Writing mode</legend>
          <div className="modes">
            {modes.map((option) => (
              <label className="mode" key={option}>
                <input
                  type="radio"
                  name="mode"
                  value={option}
                  checked={mode === option}
                  onChange={() => {
                    setMode(option);
                    clearRecommendations();
                  }}
                />
                {option}
              </label>
            ))}
          </div>
        </fieldset>

        {/* submits recommendation request */}
        <button type="submit" disabled={isLoading || isSavingSelection}>
          {isLoading ? 'Finding words…' : 'Find Words'}
        </button>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </form>

      <section
        aria-label="Recommendations"
        aria-live="polite"
        aria-busy={isLoading || isSavingSelection}
      >
        <div className="results-heading">
          <h2>Word recommendations</h2>
          <span className="badge">Top 5</span>
        </div>

        <p className="hint">
          Click a card to insert the word into your sentence. Fit Scores are estimates.
        </p>

        {isSavingSelection && <p role="status">Saving your selection…</p>}

        {recommendations.length > 0 ? (
          <div className="cards">
            {recommendations.map((recommendation) => (
              <button
                type="button"
                className="card"
                key={recommendation.word}
                onClick={() => insertWord(recommendation.word)}
                disabled={isSavingSelection || !sessionId}
                aria-pressed={selectedWord === recommendation.word}
              >
                <span className="score">
                  Fit Score · {recommendation.fit_score}/100
                </span>
                <span className="card-word">{recommendation.word}</span>
                <span className="card-explanation">
                  {recommendation.explanation}
                </span>

                {selectedWord === recommendation.word && (
                  <span className="selection-label">Selected</span>
                )}
              </button>
            ))}
          </div>
        ) : (
          <p className="empty">
            {isLoading
              ? 'Getting your recommendations…'
              : 'Your next word starts with a blank. Try the sentence above.'}
          </p>
        )}
      </section>
    </main>
  </>
);}