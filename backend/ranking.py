from models import Candidate, Recommendation


def rank_candidates(candidates: list[Candidate]) -> list[Recommendation]:
    """Score and sort all candidates. The endpoint chooses five for display."""
    recommendations = []

    for candidate in candidates:
        # Equivalent to 0.45 * context + 0.30 * style + 0.25 * grammar.
        weighted_points = (
            45 * candidate.context_score
            + 30 * candidate.style_score
            + 25 * candidate.grammar_score
        )
        # Integer arithmetic avoids float errors. Exactly .5 rounds up.
        fit_score = (weighted_points + 50) // 100
        recommendations.append(
            Recommendation(
                word=candidate.word,
                fit_score=fit_score,
                explanation=candidate.explanation,
            )
        )

    # Alphabetical ties ensure the model's original order has no influence.
    recommendations.sort(key=lambda item: (-item.fit_score, item.word.casefold()))
    return recommendations
