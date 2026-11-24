"""K-Means for the dashboard's question clusters (D2-T2, FR-ADM-03).

k is chosen by silhouette score between `k_min` and `k_max`; with fewer than `few` questions the
score is unreliable, so a fixed k is used. Same input, same clusters (fixed random_state).
"""

from collections.abc import Sequence

K_MIN, K_MAX = 3, 8
FEW_QUESTIONS = 30
FIXED_K = 3
SEED = 42


class KMeansClusterer:
    def __init__(
        self, k_min: int = K_MIN, k_max: int = K_MAX, few: int = FEW_QUESTIONS, fixed_k: int = FIXED_K
    ):
        self.k_min, self.k_max, self.few, self.fixed_k = k_min, k_max, few, fixed_k
        self.chosen_k: int | None = None  # for logs and tests
        self.scores: dict[int, float] = {}  # silhouette score per tried k

    def cluster(self, vectors: Sequence[Sequence[float]]) -> list[int]:
        import numpy as np
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        n = len(vectors)
        self.scores = {}
        if n == 0:
            self.chosen_k = 0
            return []
        data = np.asarray(vectors, dtype=float)
        distinct = len(np.unique(data, axis=0))
        if distinct < 2:  # nothing to split
            self.chosen_k = 1
            return [0] * n
        if n < self.few:
            k = min(self.fixed_k, distinct)
            self.chosen_k = k
            return KMeans(n_clusters=k, n_init=10, random_state=SEED).fit_predict(data).tolist()

        best_labels, best_score = None, -2.0
        for k in range(self.k_min, min(self.k_max, distinct - 1) + 1):
            labels = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit_predict(data)
            score = float(silhouette_score(data, labels))
            self.scores[k] = score
            if score > best_score:
                best_labels, best_score, self.chosen_k = labels, score, k
        if best_labels is None:  # fewer distinct points than k_min + 1
            self.chosen_k = min(self.fixed_k, distinct)
            best_labels = KMeans(n_clusters=self.chosen_k, n_init=10, random_state=SEED).fit_predict(data)
        return best_labels.tolist()
