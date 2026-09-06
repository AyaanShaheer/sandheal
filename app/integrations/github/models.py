from pydantic import BaseModel, Field


class GitHubWorkflowFailure(BaseModel):
    """
    Internal representation of a failed GitHub Actions workflow.

    This model intentionally hides GitHub's raw webhook structure from
    the rest of the SandHeal application.
    """

    delivery_id: str = Field(min_length=1)

    repository: str = Field(min_length=1)
    commit_sha: str = Field(min_length=1)

    workflow_name: str = Field(min_length=1)
    workflow_run_id: int = Field(gt=0)

    branch: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
