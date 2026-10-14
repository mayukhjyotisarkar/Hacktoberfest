"""
similarity.py - Question similarity analysis using TF-IDF and Representative-Based Clustering.

Identifies exact duplicates and lexically similar questions across exam papers,
groups them into recurring topic clusters using a representative-based strategy,
and exposes configurable similarity thresholds.

CLUSTERING STRATEGY: REPRESENTATIVE-BASED (LEADER) CLUSTERING
------------------------------------------------------------
Why NOT Graph Connected Components?
Graph connected components suffer from non-transitive "chain-merging":
If Question A is similar to Question B (score >= threshold), and Question B
is similar to Question C (score >= threshold), connected components merges A, B, and C
into the same group even if Question A and Question C share zero similarity!
In exam analysis, this could accidentally merge "CPU Scheduling" with "Deadlock"
if a hybrid question mentions both.

How Representative-Based Clustering Solves This:
1. Questions are sorted deterministically so the most comprehensive question becomes
   the anchor/representative of each group.
2. Every incoming question is compared against the group's representative.
3. A question is ONLY added if its similarity to that representative meets or exceeds
   the configured threshold.
4. Individual similarity scores to the representative are preserved for every question.
5. Questions in a group are NOT assumed to be equally similar to each other.

REMAINING LIMITATIONS:
1. Star-Topology Dispersion: While every member is >= threshold from the representative,
   two outer members on opposite sides of the cluster might have a mutual similarity
   slightly below the threshold.
2. Representative Selection Sensitivity: The cluster identity is anchored to the representative
   chosen during deterministic ordering.
3. Lexical vs. Semantic Gap: TF-IDF measures word overlap and term weighting. True semantic
   synonyms with zero shared vocabulary (e.g. 'CPU burst' vs 'Processor execution duration')
   cannot be recognized without semantic embeddings or domain ontology.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from paperpilot.question_parser import QuestionItem
from paperpilot.text_normalizer import normalize_for_similarity, normalize_for_exact_match


@dataclass
class QuestionCluster:
    """Represents a group of identical or similar questions anchored to a representative."""
    cluster_id: str
    representative_text: str
    representative_id: str
    questions: List[QuestionItem] = field(default_factory=list)
    similarity_to_representative: Dict[str, float] = field(default_factory=dict)
    distinct_papers: List[str] = field(default_factory=list)
    years: List[int] = field(default_factory=list)
    is_exact: bool = False
    avg_similarity: float = 1.0
    paper_count: int = 0
    occurrence_count: int = 0


@dataclass
class SimilarityAnalysisResult:
    """Complete analysis output containing clusters, statistics, and pairwise scores."""
    total_questions: int
    clusters: List[QuestionCluster]
    repeated_clusters: List[QuestionCluster]
    single_question_clusters: List[QuestionCluster]
    threshold_used: float
    pairwise_matrix: Optional[np.ndarray] = None
    question_ids: List[str] = field(default_factory=list)


def build_tfidf_matrix(normalized_texts: List[str]) -> Tuple[TfidfVectorizer, np.ndarray]:
    """
    Fits and transforms normalized questions into a TF-IDF feature matrix.
    Uses unigram term weighting with sublinear term-frequency scaling.
    """
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 1),
        stop_words="english",
        sublinear_tf=True,
        min_df=1,
    )
    tfidf_matrix = vectorizer.fit_transform(normalized_texts)
    return vectorizer, tfidf_matrix


def cluster_questions(
    questions: List[QuestionItem],
    similarity_threshold: float = 0.65,
) -> SimilarityAnalysisResult:
    """
    Groups questions into clusters using Representative-Based Clustering.

    Algorithm:
    ----------
    1. Pre-compute normalized representations for exact matching and TF-IDF similarity.
    2. Sort questions deterministically (descending length, filename, question ID)
       so the most detailed questions serve as stable cluster anchors.
    3. Iterate over questions:
       a. Compare candidate against each existing cluster's representative.
       b. Identify clusters where sim(candidate, representative) >= threshold.
       c. Assign candidate to the cluster with the highest similarity score.
       d. If no cluster meets the threshold, candidate forms a new cluster as its representative.
    4. Compile distinct papers count, occurrences, and individual similarity scores.

    Parameters:
    -----------
    questions : List[QuestionItem]
        Extracted questions from one or more exam papers.
    similarity_threshold : float
        Cosine similarity threshold between 0.0 and 1.0 (default: 0.65).

    Returns:
    --------
    SimilarityAnalysisResult
        Clusters of repeated and standalone questions with metrics.
    """
    if not questions:
        return SimilarityAnalysisResult(
            total_questions=0,
            clusters=[],
            repeated_clusters=[],
            single_question_clusters=[],
            threshold_used=similarity_threshold,
        )

    n = len(questions)
    if n == 1:
        single = questions[0]
        c = QuestionCluster(
            cluster_id="cluster_1",
            representative_text=single.text,
            representative_id=single.id,
            questions=[single],
            similarity_to_representative={single.id: 1.0},
            distinct_papers=[single.source_file],
            years=[single.year] if single.year is not None else [],
            is_exact=True,
            avg_similarity=1.0,
            paper_count=1,
            occurrence_count=1,
        )
        return SimilarityAnalysisResult(
            total_questions=1,
            clusters=[c],
            repeated_clusters=[],
            single_question_clusters=[c],
            threshold_used=similarity_threshold,
        )

    # Step 1: Pre-compute normalized forms for all questions in their original order
    norm_sim_map = {q.id: normalize_for_similarity(q.text) for q in questions}
    norm_exact_map = {q.id: normalize_for_exact_match(q.text) for q in questions}

    # Step 2: Build global TF-IDF matrix to allow computing pairwise similarities
    ordered_ids = [q.id for q in questions]
    ordered_norm_texts = [norm_sim_map[qid] for qid in ordered_ids]

    try:
        _, tfidf_matrix = build_tfidf_matrix(ordered_norm_texts)
        full_sim_matrix = cosine_similarity(tfidf_matrix)
    except ValueError:
        # Fallback if vocabulary is completely empty
        full_sim_matrix = np.eye(n)

    id_to_idx = {qid: idx for idx, qid in enumerate(ordered_ids)}

    def get_pairwise_sim(q1_id: str, q2_id: str) -> float:
        """Returns pairwise similarity between two questions."""
        # Exact match check first
        if norm_exact_map[q1_id] == norm_exact_map[q2_id] and len(norm_exact_map[q1_id]) > 0:
            return 1.0
        i1 = id_to_idx[q1_id]
        i2 = id_to_idx[q2_id]
        return float(full_sim_matrix[i1, i2])

    # Step 3: Sort questions deterministically for reproducible cluster leadership
    # Longest text first ensures the most descriptive question becomes the representative.
    sorted_questions = sorted(
        questions,
        key=lambda q: (-len(q.text), q.source_file, q.source_page, q.id)
    )

    # Step 4: Representative-based assignment
    clusters: List[QuestionCluster] = []

    for q in sorted_questions:
        best_cluster: Optional[QuestionCluster] = None
        best_score = -1.0

        for cluster in clusters:
            rep_id = cluster.representative_id
            score = get_pairwise_sim(q.id, rep_id)

            if score >= similarity_threshold and score > best_score:
                best_score = score
                best_cluster = cluster

        if best_cluster is not None and best_score >= similarity_threshold:
            # Candidate fits into an existing cluster!
            best_cluster.questions.append(q)
            best_cluster.similarity_to_representative[q.id] = round(best_score, 3)

            # Check if exact duplicate status is maintained
            if best_score < 0.999 or norm_exact_map[q.id] != norm_exact_map[best_cluster.representative_id]:
                best_cluster.is_exact = False
        else:
            # Form a new cluster with q as its representative
            new_cluster = QuestionCluster(
                cluster_id=f"cluster_{len(clusters) + 1}",
                representative_text=q.text,
                representative_id=q.id,
                questions=[q],
                similarity_to_representative={q.id: 1.0},
                is_exact=True,  # Initially true until a non-exact member joins
            )
            clusters.append(new_cluster)

    # Step 5: Finalize cluster properties (paper counts, years, average similarities)
    for c in clusters:
        c.distinct_papers = sorted(list(set(q.source_file for q in c.questions)))
        c.years = sorted(list(set(q.year for q in c.questions if q.year is not None)))
        c.paper_count = len(c.distinct_papers)
        c.occurrence_count = len(c.questions)
        scores_list = list(c.similarity_to_representative.values())
        c.avg_similarity = round(float(np.mean(scores_list)), 3) if scores_list else 1.0

        # Mark single questions as is_exact=False to avoid confusion
        if c.occurrence_count == 1:
            c.is_exact = False

    # Separate into repeated clusters (occurrence > 1) vs standalone (occurrence == 1)
    # Sort repeated clusters by paper_count (descending), occurrence_count (descending), then text
    repeated = [c for c in clusters if c.occurrence_count > 1]
    repeated.sort(key=lambda c: (-c.paper_count, -c.occurrence_count, c.representative_text))

    single = [c for c in clusters if c.occurrence_count == 1]
    single.sort(key=lambda c: c.representative_text)

    # Re-number cluster IDs cleanly
    for idx, c in enumerate(repeated + single, 1):
        c.cluster_id = f"cluster_{idx}"

    return SimilarityAnalysisResult(
        total_questions=n,
        clusters=clusters,
        repeated_clusters=repeated,
        single_question_clusters=single,
        threshold_used=similarity_threshold,
        pairwise_matrix=full_sim_matrix,
        question_ids=ordered_ids,
    )
