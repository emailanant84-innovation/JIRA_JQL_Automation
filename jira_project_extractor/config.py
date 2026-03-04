from dataclasses import dataclass


@dataclass(slots=True)
class JiraConfig:
    """Connection settings for JIRA Cloud/Server REST API."""

    base_url: str
    email: str
    api_token: str
    verify_ssl: bool = True

    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")
