from collections import Counter

def most_frequent_dependency(result_lists):
    """
    result_lists: List[List[str]]
    Returns the most frequent dependency combination (order irrelevant).
    """

    # Canonical form: sorted tuple ensures order doesn't matter
    normalized = [tuple(sorted(lst)) for lst in result_lists]

    counter = Counter(normalized)

    most_common, _ = counter.most_common(1)[0]

    return list(most_common)
