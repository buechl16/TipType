import sqlite3
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from llm import generate_candidates
from database import accept_candidate, save_session
from models import AcceptRequest, AcceptResponse, RecommendRequest, RecommendResponse
from ranking import rank_candidates


app = FastAPI(title="TipType API")

# allows the React frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],)

#generates reccs

@app.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest):
    # llm generates the candidates...
    candidates = generate_candidates(request)

    # calculates the final fit scores and rankings.
    ranked_candidates = rank_candidates(candidates)

    try:
        # saves candidates and ranking data to database
        session_id = save_session(
            request.mode,
            candidates,
            ranked_candidates,)

    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="Could not save recommendations. Please try again.",) from None

    # only 5 recommendations are shown per session!
    return RecommendResponse(
        session_id=session_id,
        recommendations=ranked_candidates[:5],
    )

# saves the user's selected word


@app.post(
    "/sessions/{session_id}/accept",
    response_model=AcceptResponse,
)
def accept_recommendation(
    session_id: UUID,
    request: AcceptRequest,
):

    try:
        # mark chosen word in database
        candidate_found = accept_candidate(str(session_id),request.word,)

    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="Could not save your selection. Please try again.",) from None

    # returns not found error
    if not candidate_found:
        raise HTTPException(
            status_code=404,
            detail="No displayed candidate matches that session and word.",
        )

    return AcceptResponse(
        session_id=session_id,
        word=request.word,
        accepted=True,
    )