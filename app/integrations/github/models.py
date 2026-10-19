from app.domain.failures import WorkflowFailure

# The failure model used to live here and was named after the provider.
# It now belongs to the domain, and this alias keeps existing imports
# working.
GitHubWorkflowFailure = WorkflowFailure

__all__ = [
    "GitHubWorkflowFailure",
    "WorkflowFailure",
]
