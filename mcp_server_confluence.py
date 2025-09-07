import os
import json
from fastmcp import FastMCP
from atlassian import Jira, Confluence
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# --- Configuration ---
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL")
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")

JIRA_SERVER = os.getenv("JIRA_SERVER")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Initialize the MCP server
mcp = FastMCP(name="confluence_server", port="8001")

# --- Helper Function: Get JIRA Project Data ---
# This is an internal function to fetch data from JIRA. It's not exposed as an MCP tool.
def get_jira_project_status(project_key: str):
    """
    Fetches all tickets for a given JIRA project.
    """
    try:
        jira = Jira(
            url=JIRA_SERVER,
            username=JIRA_USER,
            password=JIRA_API_TOKEN,
            cloud=True # Set to False for JIRA Server
        )
        jql_query = f'project = "{project_key}" ORDER BY created DESC'
        issues = jira.jql(jql_query, limit=50) # Limit to 50 for this example
        
        if not issues.get('issues'):
            return {"error": f"No issues found for project '{project_key}'."}

        status_report = []
        for issue in issues.get('issues'):
            status_report.append({
                "key": issue['key'],
                "summary": issue['fields']['summary'],
                "status": issue['fields']['status']['name'],
                "assignee": issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else 'Unassigned'
            })
        return status_report
    except Exception as e:
        return {"error": f"Failed to get JIRA status: {str(e)}"}

# --- New MCP Tool: Create a Confluence Report Page ---
@mcp.tool(
    description="Creates a new Confluence page with a JIRA project status report.",
    name="create_confluence_report"
)
async def create_confluence_report(
    page_title: str,
    confluence_space_key: str,
    jira_project_key: str
) -> dict:
    """
    Creates a Confluence page and posts a formatted JIRA project status report.
    
    Args:
        page_title: Take the input from user to provide title of the page(e.g., 'PROJECT STATUS REPORT'). 
        confluence_space_key: The key of the Confluence space (e.g., 'SPACE').
        jira_project_key: The key of the JIRA project (e.g., 'PROJ').
        
    Returns:
        A dictionary containing the URL of the new Confluence page, or an error.
    """
    try:
        # Step 1: Get the JIRA project status
        jira_report = get_jira_project_status(jira_project_key)
        
        if "error" in jira_report:
            return jira_report # Return the error from the helper function

        # Step 2: Format the JIRA data into HTML for the Confluence page body
        html_content = "<h2>JIRA Project Status Report: " + jira_project_key + "</h2>"
        html_content += "<table border='1' cellpadding='5' cellspacing='0' style='width: 100%; border-collapse: collapse;'>"
        html_content += "<thead><tr><th>Issue Key</th><th>Summary</th><th>Status</th><th>Assignee</th></tr></thead>"
        html_content += "<tbody>"
        
        for item in jira_report:
            html_content += "<tr>"
            html_content += f"<td><a href='{JIRA_SERVER}/browse/{item['key']}'>{item['key']}</a></td>"
            html_content += f"<td>{item['summary']}</td>"
            html_content += f"<td>{item['status']}</td>"
            html_content += f"<td>{item['assignee']}</td>"
            html_content += "</tr>"
        
        html_content += "</tbody></table>"

        # Step 3: Create the Confluence page
        confluence = Confluence(
            url=CONFLUENCE_URL,
            username=CONFLUENCE_USERNAME,
            password=CONFLUENCE_API_TOKEN,
            cloud=True # Set to False for Confluence Server
        )

        #page_title = f"JIRA Status Report - {jira_project_key}"
        
        create_result = confluence.create_page(
            space=confluence_space_key,
            title=page_title,
            body=html_content,
            parent_id=None, # You can add a parent page ID if needed
            type="page",
            representation="storage" # Use storage format to render HTML correctly
        )

        # Check if the page was created successfully
        if create_result and 'id' in create_result:
            page_url = f"{CONFLUENCE_URL}/spaces/{confluence_space_key}/pages/{create_result['id']}"
            return {
                "page_title": page_title,
                "page_url": page_url,
                "message": "Confluence page created successfully."
            }
        else:
            return {"error": "Failed to create Confluence page. Check permissions and space key."}

    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

# Run the MCP server
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
