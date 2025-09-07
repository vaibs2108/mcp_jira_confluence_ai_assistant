import streamlit as st
from openai import OpenAI
from fastmcp import Client
from dotenv import load_dotenv
import asyncio
import os
import json
from jira import JIRAError

# Load environment variables from .env file
load_dotenv(override=True)

# OpenAI client for tool usage and response generation
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# --- Client Configuration ---
server_config = {
    "jira_server": {
        "url": "http://127.0.0.1:8000/mcp"
    },
    "confluence_server": {
        "url": "http://127.0.0.1:8001/mcp"
    }
}

# --- Streamlit Page Setup ---
st.set_page_config(page_title="JIRA & Confluence AI Assistant")
st.title("JIRA & Confluence AI Assistant")
st.caption("Manages tickets, pages, statuses, or tasks - Powered by MCP, GPT-4o-mini & Streamlit")

# Initialize session state variables for chat history and tool management
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "available_tools" not in st.session_state:
    st.session_state.available_tools = []
if "llm_tools_schema" not in st.session_state:
    st.session_state.llm_tools_schema = []

# --- Function to fetch available tools and build the LLM schema ---
async def fetch_tools():
    """Fetches all available tools from all configured servers and builds the LLM schema."""
    with st.spinner("Connecting to servers and fetching tools..."):
        try:
            async with Client(server_config) as client:
                tools = await client.list_tools()
                st.session_state.available_tools = tools
                update_llm_tools_schema(tools)
        except Exception as e:
            st.error(f"Error connecting to one or more MCP servers: {e}")
            st.warning("Please ensure your JIRA and Confluence servers are running on ports 8000 and 8001 respectively.")
            st.session_state.available_tools = []
            st.session_state.llm_tools_schema = []

def update_llm_tools_schema(tools_list):
    """Dynamically builds the LLM tool schema from available tools."""
    llm_tools = []
    for tool in tools_list:
        # Safely get the parameters, prioritizing 'parameters' but falling back to 'inputSchema'
        parameters = getattr(tool, 'parameters', None)
        if parameters is None:
            parameters = getattr(tool, 'inputSchema', {})
        
        if not isinstance(parameters, dict):
            parameters = {}
        
        llm_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": parameters.get("properties", {}),
                    "required": parameters.get("required", [])
                }
            }
        })
    st.session_state.llm_tools_schema = llm_tools

# Fetch tools on first run or on button click
if not st.session_state.available_tools:
    asyncio.run(fetch_tools())

# --- Sidebar for Tools and Status ---
st.sidebar.title("Available Tools")
st.sidebar.markdown(f"**Found {len(st.session_state.available_tools)} tool(s)** from connected servers.")
if not st.session_state.available_tools:
    st.sidebar.warning("No tools found. Please check if your servers are running.")

# Refresh button to re-fetch tools
if st.sidebar.button("Refresh Tools"):
    asyncio.run(fetch_tools())
    st.rerun() # Rerun to update the UI with new tools

# Dynamically create radio options for the sidebar
tool_names = [tool.name for tool in st.session_state.available_tools]
tool_options = ['Chat with AI'] + tool_names
tool_option = st.sidebar.radio(
    "Select a tool to use directly:",
    tool_options,
    key='tool_selection'
)

# --- Direct Tool Call Forms based on selected option ---
if tool_option != 'Chat with AI':
    selected_tool = next((t for t in st.session_state.available_tools if t.name == tool_option), None)
    if selected_tool:
        st.sidebar.subheader(f"Call: {selected_tool.name}")
        st.sidebar.info(selected_tool.description)

        # --- NEW: Display raw tool metadata for debugging ---
        #st.sidebar.subheader("Tool Metadata (for debugging)")
        #st.sidebar.json(selected_tool)
        # --- END NEW ---

        with st.sidebar.form(f"form_{selected_tool.name}"):
            # Safely get the parameters and generate form inputs
            params = getattr(selected_tool, 'parameters', None)
            if params is None:
                params = getattr(selected_tool, 'inputSchema', {})
            
            properties = params.get("properties", {})
            form_args = {}
            
            # Check if the tool has any parameters
            if properties:
                for param_name, param_info in properties.items():
                    form_args[param_name] = st.text_input(
                        f"Enter {param_name} ({param_info.get('type', 'string')})",
                        key=f"{selected_tool.name}_{param_name}"
                    )
            else:
                st.info("This tool requires no inputs. Simply click the button to execute it.")
            
            submitted = st.form_submit_button(f"Call {selected_tool.name}")
            
            if submitted:
                # Construct the user query for direct tool call
                arg_list = [f"{k}='{v}'" for k, v in form_args.items() if v]
                user_query = f"{selected_tool.name}({', '.join(arg_list)})"
                st.session_state.chat_history.append({"role": "user", "content": user_query})
                # Rerun to process the new user message immediately
                st.rerun()

# --- Main Chat Area ---
if tool_option == 'Chat with AI':
    user_query = st.chat_input("Ask me about your JIRA or Confluence projects...")
    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        st.rerun() # Rerun to process the new chat message

async def process_query(user_query):
    """Processes a user query by calling an LLM or a direct tool."""
    async with Client(server_config) as client:
        mcp_result = None
        tool_name = None
        tool_args = {}

        # First, check if the query is a direct tool call string
        for tool in st.session_state.available_tools:
            if user_query.strip().startswith(f"{tool.name}("):
                try:
                    tool_name = tool.name
                    # Robust parsing of key=value pairs from the user query string
                    args_str = user_query.split('(', 1)[1].rstrip(')')
                    args_pairs = [arg.strip() for arg in args_str.split(',')]
                    tool_args = {}
                    for arg in args_pairs:
                        if '=' in arg:
                            key, value = arg.split('=', 1)
                            key = key.strip()
                            # Use ast.literal_eval for safe evaluation of strings and numbers
                            try:
                                # This handles cases where a string value might be quoted
                                tool_args[key] = eval(value.strip())
                            except:
                                # If eval fails, treat it as a plain string
                                tool_args[key] = value.strip().strip("'\"")
                    
                    # --- NEW: Specific try/except block for the tool call ---
                    try:
                        st.info(f"Calling tool: {tool_name} with args: {tool_args}")
                        mcp_result = await client.call_tool(tool_name, tool_args)
                        st.success(f"Tool call succeeded.")
                    except Exception as tool_call_error:
                        st.error(f"Tool call failed with an unexpected error: {tool_call_error}")
                        st.exception(tool_call_error) # Display the full traceback
                        mcp_result = {"error": str(tool_call_error)}
                    # --- END NEW ---

                    break
                except Exception as e:
                    mcp_result = {"error": f"Invalid arguments for {tool_name}: {e}"}
                    break

        # If no direct tool call was found, use the LLM to decide
        if mcp_result is None:
            system_prompt = """
            You are a project assistant. You can call these tools:
            """ + "\n".join([
                f"{i+1}. {t.name}(" + 
                ", ".join([
                    f"{p_name}: {p_info.get('type', 'string')}" 
                    for p_name, p_info in (getattr(t, 'parameters', None) or getattr(t, 'inputSchema', {})).get('properties', {}).items()
                ]) + 
                f") - {t.description}"
                for i, t in enumerate(st.session_state.available_tools)
            ]) + """

            When the user asks something related to project data, decide the right tool call, get the data, and then answer naturally. If no tool is needed, respond as a normal assistant.
            """

            messages_for_llm = [{"role": "system", "content": system_prompt}] + st.session_state.chat_history
            
            try:
                tool_decision = openai_client.chat.completions.create(
                    model="gpt-4o-mini", 
                    messages=messages_for_llm,
                    tools=st.session_state.llm_tools_schema,
                    tool_choice="auto"
                )

                response_message = tool_decision.choices[0].message
                tool_calls = getattr(response_message, 'tool_calls', [])
                
                if tool_calls:
                    for tool_call in tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        # --- NEW: Specific try/except block for the tool call ---
                        try:
                            st.info(f"LLM is calling tool: {tool_name} with args: {tool_args}")
                            mcp_result = await client.call_tool(tool_name, tool_args)
                            st.success(f"Tool call succeeded.")
                        except Exception as tool_call_error:
                            st.error(f"LLM-based tool call failed with an unexpected error: {tool_call_error}")
                            st.exception(tool_call_error) # Display the full traceback
                            mcp_result = {"error": str(tool_call_error)}
                        # --- END NEW ---
                else:
                    mcp_result = response_message.content

            except Exception as e:
                mcp_result = {"error": f"LLM-based tool call failed: {e}"}

        # Process the result from the tool or LLM
        if isinstance(mcp_result, str):
            tool_result_data = mcp_result
        elif hasattr(mcp_result, 'data'):
            tool_result_data = mcp_result.data
        else:
            tool_result_data = str(mcp_result)

        # Use the LLM to generate a final conversational response
        if isinstance(tool_result_data, dict) and "error" in tool_result_data:
            final_prompt = f"User asked: {user_query}\n\nTool '{tool_name}' failed with error:\n{tool_result_data['error']}\n\nInform the user of the failure and suggest next steps."
        elif tool_name:
            final_prompt = f"User asked: {user_query}\n\nTool result from '{tool_name}':\n{json.dumps(tool_result_data, indent=2)}\n\nAnswer concisely, acknowledging the tool use."
        else:
            final_prompt = user_query

        try:
            final_answer = openai_client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[{"role": "user", "content": final_prompt}]
            )
            bot_reply = final_answer.choices[0].message.content
        except Exception as e:
            bot_reply = f"I encountered an error generating a response: {str(e)}"

        return bot_reply

# Display chat history
for msg in st.session_state.chat_history:
    st.chat_message(msg["role"]).write(msg["content"])

# Process the last user message if it hasn't been answered yet
if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
    last_msg = st.session_state.chat_history[-1]["content"]
    with st.spinner("Processing your request..."):
        try:
            bot_reply = asyncio.run(process_query(last_msg))
            st.session_state.chat_history.append({"role": "assistant", "content": bot_reply})
            st.rerun()
        except Exception as e:
            st.error(f"Error processing request: {str(e)}")
            st.session_state.chat_history.append({"role": "assistant", "content": f"I'm sorry, I was unable to complete your request due to a technical error: {str(e)}"})
            st.rerun()
