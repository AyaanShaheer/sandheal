from pydantic import BaseModel, Field


class WorkflowFailure(BaseModel):
    """
    Domain representation of a failed CI workflow.

    This model is intentionally free of any GitHub specific structure, so
    the domain and the persistence layers do not depend on an external
    provider.
    """

    delivery_id: str = Field(min_length=1)

    repository: str = Field(min_length=1)
    commit_sha: str = Field(min_length=1)

    workflow_name: str = Field(min_length=1)
    workflow_run_id: int = Field(gt=0)

    branch: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
