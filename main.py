from jira_project_extractor.gui import JiraExtractionGUI
from jira_project_extractor.logging_utils import get_logger

logger = get_logger("main")


if __name__ == "__main__":
    try:
        JiraExtractionGUI().run()
    except Exception:
        logger.exception("Application terminated due to unhandled exception")
        raise
