from mcp.server.fastmcp import FastMCP
from jira import JIRA, JIRAError
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Create MCP server
mcp = FastMCP("jira_server", port="8000")

# Connect to JIRA
jira_server = os.environ.get("JIRA_SERVER")
jira_user = os.environ.get("JIRA_USER")
jira_token = os.environ.get("JIRA_API_TOKEN")

# Use a global client instance for all tools
try:
    jira_client = JIRA(server=jira_server, basic_auth=(jira_user, jira_token))
except JIRAError as e:
    print(f"JIRA connection failed: {e}")
    jira_client = None

@mcp.tool()
def get_ticket_status(issue_key: str) -> dict:
    """
    Get the current status of a JIRA ticket.
    Args:
        issue_key: JIRA issue key (e.g., DEMO-101)
    """
    if not jira_client:
        return {"error": "JIRA client is not connected."}
    try:
        issue = jira_client.issue(issue_key)
        return {
            "key": issue.key,
            "summary": issue.fields.summary,
            "status": issue.fields.status.name
        }
    except JIRAError as e:
        return {"error": f"Failed to retrieve ticket {issue_key}: {e.text}"}

@mcp.tool()
def get_project_status(project_key: str) -> list:
    """
    Get all tickets for a project with their statuses.
    Args:
        project_key: JIRA project key (e.g., DEMO)
    """
    if not jira_client:
        return {"error": "JIRA client is not connected."}
    try:
        # The JQL query is case-sensitive for project keys, so ensure it's correct.
        issues = jira_client.search_issues(f'project={project_key}', maxResults=50)
        return [
            {
                "key": issue.key,
                "summary": issue.fields.summary,
                "status": issue.fields.status.name
            }
            for issue in issues
        ]
    except JIRAError as e:
        return {"error": f"Failed to retrieve project {project_key} issues: {e.text}"}

@mcp.tool()
def create_ticket(project_key: str, summary: str, description: str, issue_type: str = 'Task') -> dict:
    """
    Create a new JIRA ticket.
    Args:
        project_key: The project key where the ticket will be created.
        summary: A brief summary for the ticket.
        description: A detailed description of the ticket.
        issue_type: The type of issue to create (e.g., 'Task', 'Bug', 'Story').
    """
    if not jira_client:
        return {"error": "JIRA client is not connected."}
    try:
        issue_dict = {
            'project': {'key': project_key},
            'summary': summary,
            'description': description,
            'issuetype': {'name': issue_type},
        }
        new_issue = jira_client.create_issue(fields=issue_dict)
        return {
            "success": True,
            "key": new_issue.key,
            "link": new_issue.self
        }
    except JIRAError as e:
        return {"error": f"Failed to create ticket: {e.text}"}

@mcp.tool()
def delete_ticket(issue_key: str) -> dict:
    """
    Delete a specific JIRA ticket. This action is irreversible.
    Args:
        issue_key: The key of the ticket to delete (e.g., DEMO-101).
    """
    if not jira_client:
        return {"error": "JIRA client is not connected."}
    try:
        issue = jira_client.issue(issue_key)
        issue.delete()
        return {"success": True, "message": f"Ticket {issue_key} has been deleted."}
    except JIRAError as e:
        return {"error": f"Failed to delete ticket {issue_key}: {e.text}"}

if __name__ == "__main__":
    if jira_client:
        print("🚀 JIRA MCP Server is running...")
        mcp.run(transport="streamable-http")
        #mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")
    else:
        print("❌ JIRA MCP Server could not start due to connection issues.")