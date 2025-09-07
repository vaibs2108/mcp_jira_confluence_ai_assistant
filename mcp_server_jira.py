import os
import json
from fastmcp import FastMCP
from jira import JIRA, JIRAError
from dotenv import load_dotenv

# Define a custom exception for our tools
class JiraToolError(Exception):
    """A custom exception for JIRA tool-related errors."""
    pass

# Load environment variables from .env file
load_dotenv(override=True)

# Create a FastMCP server instance
mcp_server = FastMCP("Jira Server", port="8000")

# --- JIRA Client Initialization ---
def get_jira_client():
    """Initializes and returns a JIRA client instance."""
    jira_url = os.environ.get("JIRA_URL")
    jira_user = os.environ.get("JIRA_USER")
    jira_token = os.environ.get("JIRA_TOKEN")

    if not all([jira_url, jira_user, jira_token]):
        raise JiraToolError("JIRA credentials not configured. Please set JIRA_URL, JIRA_USER, and JIRA_TOKEN in your .env file.")

    try:
        return JIRA(server=jira_url, basic_auth=(jira_user, jira_token))
    except JIRAError as e:
        raise JiraToolError(f"Failed to connect to JIRA: {e.text}")

# --- Tool Definitions ---

@mcp_server.tool("create_ticket", description="Creates a new JIRA issue.")
def create_ticket(project_key: str, summary: str, description: str, issue_type: str = 'Story'):
    """
    Creates a new JIRA ticket with a specified project key, summary, and description.
    Args:
        project_key (str): The project key (e.g., 'TEST').
        summary (str): The summary/title of the new ticket.
        description (str): A detailed description for the ticket.
        issue_type (str): The type of issue to create (e.g., 'Story', 'Task', 'Bug', 'Epic'). Defaults to 'Story'.
    Returns:
        A dictionary containing the ticket key and URL on success.
    """
    try:
        jira = get_jira_client()
        issue_dict = {
            'project': {'key': project_key},
            'summary': summary,
            'description': description,
            'issuetype': {'name': issue_type},
        }
        new_issue = jira.create_issue(fields=issue_dict)
        return {
            "key": new_issue.key,
            "url": new_issue.permalink()
        }
    except JIRAError as e:
        if e.text:
            error_message = f"JIRA API Error: {e.text}"
            if 'The issue type selected is not valid' in e.text:
                error_message += ". This could be because the issue type is not available in the specified project."
            raise JiraToolError(error_message)
        else:
            raise JiraToolError(f"JIRA API Error: {e.status_code} - No detailed message provided.")
    except Exception as e:
        raise JiraToolError(f"An unexpected error occurred during ticket creation: {str(e)}")


@mcp_server.tool("get_project_status", description="Returns a summary of the project's status, including issue counts by type and status.")
def get_project_status(project_key: str):
    """
    Fetches the status of a JIRA project.
    Args:
        project_key (str): The project key (e.g., 'TEST').
    Returns:
        A dictionary with counts of issues by type and status, or a message indicating no issues found.
    """
    try:
        jira = get_jira_client()
        # Use JQL to get all issues in the project
        jql_query = f'project = "{project_key}" ORDER BY created DESC'
        issues = jira.search_issues(jql_query, maxResults=100)
        
        if not issues:
            return {"message": f"No issues found for project '{project_key}'."}

        # Initialize dictionaries to hold counts
        status_counts = {}
        type_counts = {}

        for issue in issues:
            # Count by status
            status_name = issue.fields.status.name
            status_counts[status_name] = status_counts.get(status_name, 0) + 1

            # Count by issue type
            issue_type_name = issue.fields.issuetype.name
            type_counts[issue_type_name] = type_counts.get(issue_type_name, 0) + 1

        return {
            "project_key": project_key,
            "total_issues": len(issues),
            "status_counts": status_counts,
            "type_counts": type_counts
        }

    except JIRAError as e:
        # Catch JIRAError and provide a clear message
        error_message = f"JIRA API Error fetching project status for '{project_key}': {e.text}"
        if 'The project with key' in e.text or 'does not exist' in e.text:
            error_message = f"JIRA API Error: The project with key '{project_key}' does not exist or you do not have permission to view it."
        raise JiraToolError(error_message)
    except Exception as e:
        # Catch any other unexpected errors
        raise JiraToolError(f"An unexpected error occurred: {str(e)}")

# This function is not a tool but demonstrates a non-tool function
def get_some_other_info():
    return "This is a simple helper function."

# Add the main execution block to run the server
if __name__ == "__main__":
    try:
        # Check for client connectivity before starting the server
        jira_client = get_jira_client()
        if jira_client:
            print("🚀 JIRA MCP Server is running...")
            mcp_server.run(transport="streamable-http")
        else:
            print("❌ JIRA MCP Server could not start due to connection issues.")
    except JiraToolError as e:
        print(f"❌ Server initialization failed: {e}")
