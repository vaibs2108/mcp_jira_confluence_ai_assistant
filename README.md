JIRA & Confluence AI Assistant
Welcome to AI Assistant for jira & Confluence using MCP! This project leverages AI to automate and enhance the process of ticket creation in Jira, getting project status update from Jira and creating & updating the same in Confluence page. It will Model Context Protocol 2.0. Orcrestration is done by OpenAI LLM 

🚀 Features
Jira Integration: Creates Jira ticket, Fetches project status directly from Jira. 
Confluence Integration: Creates new confluence page & update it with the Fetched project status details directly from Jira to Confluence.
OpenAI LLM: Use the LLM to generate a final conversational response
MCP server : Jira & confluence are used as MCP servers
MCP client : it comprises of MCP Client to interact with tools, LLM as Orcestrator & Streamlit as UI 
Output: create a Jira ticket, get the project status updates from Jira and if called it can directly update the confluence page


🛠️ Tech Stack
Python
Streamlit for the web UI
LLM for AI agents
Jira API
Confluence API

📦 Project Structure
mcp_client.py                # Streamlit app entry point
mcp_server_jira.py           # AI agent logic for test area and test case generation
mcp_server_confluence.py     # Integrations for Jira and GitHub


⚡ Quick Start
Clone the repo and move to the directory
Install dependencies:
pip install -r requirements.txt
Set up environment variables:
Copy .env.example to .env and fill in your API keys.
Run the app:
uv run mcp_server_jira.py # start the jira server
uv run mcp_server_confluence.py #start the confluence server
streamlit run mcp_client.py   # run the client


metadata
title: JIRA & Confluence AI Assistant
sdk: mcp, openai & streamlit
app_file: mcp_client.py

