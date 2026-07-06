from flask import Flask, render_template, request, jsonify
import os
import pickle
import re
import difflib
import pandas as pd

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:  # pragma: no cover - fallback for minimal environments
    TfidfVectorizer = None
    cosine_similarity = None

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "movies.csv")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "movie_recommendation_model.pkl")


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def load_movie_data():
    if not os.path.exists(DATA_PATH):
        return pd.DataFrame()

    df = pd.read_csv(DATA_PATH)
    required_columns = [
        "title", "genres", "original_language", "runtime", "popularity",
        "vote_average", "vote_count", "release_date", "overview"
    ]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in movie dataset: {missing}")

    movie_df = df[required_columns].copy()
    movie_df["genres_list"] = movie_df["genres"].fillna("").astype(str).apply(lambda value: [
        genre.strip() for genre in value.replace("Science Fiction", "ScienceFiction").replace("TV Movie", "TVMovie").split()
        if genre.strip()
    ])
    movie_df["language"] = movie_df["original_language"].fillna("").astype(str).str.lower()
    movie_df["runtime"] = pd.to_numeric(movie_df["runtime"], errors="coerce").fillna(120)
    movie_df["popularity"] = pd.to_numeric(movie_df["popularity"], errors="coerce").fillna(0)
    movie_df["vote_average"] = pd.to_numeric(movie_df["vote_average"], errors="coerce").fillna(6.0)
    movie_df["vote_count"] = pd.to_numeric(movie_df["vote_count"], errors="coerce").fillna(0)
    movie_df["release_year"] = pd.to_datetime(movie_df["release_date"], errors="coerce").dt.year.fillna(2000)
    movie_df["decade"] = ((movie_df["release_year"] // 10) * 10).astype(int).astype(str) + "s"
    movie_df["overview"] = movie_df["overview"].fillna("").astype(str)
    movie_df = movie_df.dropna(subset=["title"]).copy()
    return movie_df


def build_movie_model():
    model_data = load_movie_data()
    with open(MODEL_PATH, "wb") as file:
        pickle.dump(model_data, file)
    return model_data


def load_movie_model():
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as file:
                return pickle.load(file)
        except Exception as exc:
            print(f"Failed to load pickle model ({exc}); rebuilding instead.")
    return build_movie_model()


MOVIES = load_movie_model()


def build_content_recommender():
    if not os.path.exists(DATA_PATH):
        return pd.DataFrame(), None

    if TfidfVectorizer is None or cosine_similarity is None:
        return pd.DataFrame(), None

    df = pd.read_csv(DATA_PATH)
    required_columns = ["title", "genres", "keywords", "tagline", "cast", "director", "overview"]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns for content recommender: {missing}")

    recommender_df = df[required_columns].copy()
    for column in ["genres", "keywords", "tagline", "cast", "director", "overview"]:
        recommender_df[column] = recommender_df[column].fillna("").astype(str)

    recommender_df["combined_features"] = (
        recommender_df["genres"] + " " +
        recommender_df["keywords"] + " " +
        recommender_df["tagline"] + " " +
        recommender_df["cast"] + " " +
        recommender_df["director"]
    )

    vectorizer = TfidfVectorizer(stop_words="english")
    feature_vector = vectorizer.fit_transform(recommender_df["combined_features"])
    similarity = cosine_similarity(feature_vector)
    return recommender_df, (vectorizer, similarity)


try:
    CONTENT_MOVIES, CONTENT_RECOMMENDER = build_content_recommender()
except Exception as exc:
    print(f"Content recommender setup failed ({exc}); falling back to preference-based recommendations.")
    CONTENT_MOVIES = pd.DataFrame()
    CONTENT_RECOMMENDER = None


def recommend_similar_movies(movie_name, top_n=6):
    if CONTENT_MOVIES.empty or CONTENT_RECOMMENDER is None:
        return []

    title_list = CONTENT_MOVIES["title"].astype(str).tolist()
    close_matches = difflib.get_close_matches(str(movie_name).strip(), title_list, n=1, cutoff=0.4)
    if not close_matches:
        return []

    close_match = close_matches[0]
    match_index = CONTENT_MOVIES[CONTENT_MOVIES["title"] == close_match].index[0]
    _, similarity = CONTENT_RECOMMENDER
    similarity_scores = list(enumerate(similarity[match_index]))
    sorted_similar_movies = sorted(similarity_scores, key=lambda item: item[1], reverse=True)[1:top_n + 1]

    recommendations = []
    for index, score in sorted_similar_movies:
        movie = CONTENT_MOVIES.iloc[index]
        recommendations.append({
            "title": movie["title"],
            "score": round(float(score), 3),
            "details": movie["genres"] or "Popular movie"
        })

    return recommendations


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    if MOVIES.empty:
        result = {
            "success": False,
            "error": "The movie dataset is not available."
        }
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(result)
        return render_template("index.html", flask_result=result)

    movie_name = request.form.get("movieName", "").strip()
    if movie_name:
        recommendations = recommend_similar_movies(movie_name, top_n=6)
        if recommendations:
            first_recommendation = recommendations[0]
            match_percentage = round(min(99.0, max(10.0, first_recommendation["score"] * 100)), 1)
            match_level = "High Match" if match_percentage >= 75 else "Medium Match" if match_percentage >= 50 else "Low Match"
            prediction_text = f"Based on '{movie_name}', these are the closest matches: {', '.join(item['title'] for item in recommendations[:5])}"
            result = {
                "success": True,
                "match_percentage": match_percentage,
                "match_level": match_level,
                "prediction_text": prediction_text,
                "movie_title": first_recommendation["title"],
                "movie_details": f"Similarity {first_recommendation['score']:.2f} · {first_recommendation['details']}",
                "recommendations": recommendations,
            }
        else:
            result = {
                "success": False,
                "error": f"I could not find a close movie match for '{movie_name}'. Try another title."
            }
    else:
        preferences = {
            "genre": request.form.get("genre", "").strip(),
            "language": request.form.get("language", "").strip(),
            "releaseEra": request.form.get("releaseEra", "Any").strip(),
            "runtime": float(request.form.get("runtime", "120")),
            "minRating": float(request.form.get("minRating", "7.0")),
            "popularity": float(request.form.get("popularity", "100")),
            "minVotes": float(request.form.get("minVotes", "1000")),
        }

        preferred_genre = slugify(preferences["genre"])
        preferred_language = preferences["language"].lower()
        preferred_era = preferences["releaseEra"]

        scored_movies = []
        for _, movie in MOVIES.iterrows():
            movie_genres = [slugify(genre) for genre in movie["genres_list"]]
            movie_language = str(movie["language"]).lower()
            movie_runtime = float(movie["runtime"])
            movie_rating = float(movie["vote_average"])
            movie_popularity = float(movie["popularity"])
            movie_votes = float(movie["vote_count"])
            movie_decade = str(movie["decade"])

            score = 0.0
            if preferred_genre and preferred_genre in movie_genres:
                score += 35
            if preferred_language and preferred_language == movie_language:
                score += 20
            if preferred_era != "Any" and preferred_era == movie_decade:
                score += 10

            runtime_gap = abs(movie_runtime - preferences["runtime"])
            score += max(0, 15 - runtime_gap / 8)

            rating_gap = abs(movie_rating - preferences["minRating"])
            score += max(0, 15 - rating_gap * 4)

            popularity_gap = abs(movie_popularity - preferences["popularity"])
            score += max(0, 10 - popularity_gap / 20)

            if movie_votes >= preferences["minVotes"]:
                score += 5

            if score < 0:
                score = 0

            scored_movies.append((score, movie))

        scored_movies.sort(key=lambda item: item[0], reverse=True)
        best_score, best_movie = scored_movies[0] if scored_movies else (0.0, None)

        if best_movie is None:
            result = {"success": False, "error": "No movie data available."}
        else:
            match_percentage = round(min(99.0, max(10.0, best_score)), 1)
            match_level = "High Match" if match_percentage >= 75 else "Medium Match" if match_percentage >= 50 else "Low Match"
            summary = best_movie["overview"][:140].strip() or "A crowd favorite with strong audience appeal."
            prediction_text = f"Recommended movie: {best_movie['title']} — {summary}"
            result = {
                "success": True,
                "match_percentage": match_percentage,
                "match_level": match_level,
                "prediction_text": prediction_text,
                "movie_title": best_movie["title"],
                "movie_details": f"{best_movie['vote_average']:.1f}/10 rating · {int(best_movie['runtime'])} min · {best_movie['decade']}"
            }

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(result)

    return render_template(
        "index.html",
        prediction_text=result.get("prediction_text", ""),
        match_percentage=result.get("match_percentage", 0),
        match_level=result.get("match_level", ""),
        flask_result=result,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
