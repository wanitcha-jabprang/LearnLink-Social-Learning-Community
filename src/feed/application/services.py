from feed.domain.policies import normalize_search_term


class FeedService:
    def __init__(self, repository):
        self.repository = repository

    def home_context(self, user, query="", saved_only=False):
        normalized_query = (
            normalize_search_term(query.strip()) if query else ""
        )
        return self.repository.home_context(
            user,
            normalized_query,
            saved_only,
        )
