"""Chat page with streaming support and conversation history."""
import streamlit as st
from src.utils.api_client import api_client
from src.utils.helpers import parse_stream_event, format_message
import json
from datetime import datetime


def init_chat_state():
    """Initialize chat-related session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_conversation_id" not in st.session_state:
        st.session_state.current_conversation_id = None
    if "conversations" not in st.session_state:
        st.session_state.conversations = []


def load_conversations():
    """Load user's conversations from backend."""
    if st.session_state.username:
        convs = api_client.get_conversations(st.session_state.username)
        st.session_state.conversations = convs if convs else []


def load_messages(conversation_id: int):
    """Load messages for a conversation."""
    messages = api_client.get_messages(conversation_id)
    st.session_state.messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
    ]
    st.session_state.current_conversation_id = conversation_id


def create_new_conversation():
    """Create a new conversation."""
    title = f"Chat {datetime.now().strftime('%m/%d %H:%M')}"
    result = api_client.create_conversation(st.session_state.username, title)
    if "id" in result:
        st.session_state.current_conversation_id = result["id"]
        st.session_state.messages = []
        load_conversations()
        return result["id"]
    return None


def save_message(role: str, content: str):
    """Save a message to the current conversation."""
    if st.session_state.current_conversation_id:
        api_client.add_message(
            st.session_state.current_conversation_id,
            role,
            content
        )


def show_chat():
    """Display chat interface."""
    init_chat_state()
    
    st.title("💬 Chat with Agent")
    
    # Sidebar - Conversation Management
    with st.sidebar:
        
        # Conversation list
        st.subheader("Conversations", divider=False)

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("➕ New", use_container_width=True, help="New conversation"):
                create_new_conversation()
                st.rerun()
        with col2:
            if st.button("🔄 Refresh", use_container_width=True, help="Reload conversations"):
                load_conversations()
                st.rerun()

        load_conversations()
        
        if not st.session_state.conversations:
            st.caption("No conversations yet. Create a new one!")
        else:
            for conv in st.session_state.conversations:
                col1, col2 = st.columns([4, 1])
                with col1:
                    is_active = conv["id"] == st.session_state.current_conversation_id
                    btn_type = "primary" if is_active else "secondary"
                    if st.button(
                        f"{'●' if is_active else '○'} {conv['title'][:20]}",
                        key=f"conv_{conv['id']}",
                        use_container_width=True,
                        type=btn_type
                    ):
                        load_messages(conv["id"])
                        st.rerun()
                
                with col2:
                    if st.button("✕", key=f"del_{conv['id']}", help="Delete"):
                        api_client.delete_conversation(conv["id"])
                        if st.session_state.current_conversation_id == conv["id"]:
                            st.session_state.current_conversation_id = None
                            st.session_state.messages = []
                        load_conversations()
                        st.rerun()
        
        st.divider()
        
        # Chat actions
        st.subheader("Actions", divider=False)
        
        if st.session_state.current_conversation_id:
            if st.button("🧹 Clear Messages", use_container_width=True, help="Clear current chat"):
                if st.session_state.current_conversation_id:
                    api_client.clear_messages(st.session_state.current_conversation_id)
                st.session_state.messages = []
                st.rerun()
            
            if st.button("📥 Export", use_container_width=True, help="Export as JSON"):
                chat_json = json.dumps(st.session_state.messages, indent=2, ensure_ascii=False)
                st.download_button(
                    label="Download JSON",
                    data=chat_json,
                    file_name="chat_history.json",
                    mime="application/json",
                    use_container_width=True
                )
        else:
            st.caption("No conversation selected")
        
        st.divider()
    
    # Main chat area
    if not st.session_state.current_conversation_id:
        st.info("👈 Select a conversation or create a new one to start chatting!")
        
        # Quick start
        if st.button("🚀 Start New Conversation", type="primary"):
            create_new_conversation()
            st.rerun()
        return
    
    # Display chat history
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    st.divider()
    
    # Input area
    user_input = st.chat_input("Ask me anything about hospital or DSM-5...")
    
    if user_input:
        # Add user message
        st.session_state.messages.append(format_message(user_input, "user"))
        save_message("user", user_input)
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Stream response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            tool_info = []
            
            try:
                # Show thinking status
                with st.status("Thinking...", expanded=True) as status:
                    for line in api_client.stream_chat(user_input, st.session_state.username):
                        event = parse_stream_event(line)
                        if event:
                            if event.get("type") == "tool":
                                tool_name = event.get("tool", "Unknown")
                                tool_input = event.get("input", "")[:100]
                                tool_info.append(f"🔧 Using: **{tool_name}**")
                                st.write(f"🔧 Using tool: **{tool_name}**")
                                st.caption(f"Input: {tool_input}...")
                            
                            elif event.get("type") == "result":
                                result = event.get("result", "")[:100]
                                st.write(f"📊 Got result...")
                            
                            elif event.get("type") == "answer":
                                full_response = event.get("answer", "")
                            
                            elif event.get("type") == "error":
                                st.error(f"Error: {event.get('error')}")
                    
                    status.update(label="✅ Complete!", state="complete", expanded=False)
                
                # Display final response
                if full_response:
                    message_placeholder.markdown(full_response)
                    st.session_state.messages.append(format_message(full_response, "assistant"))
                    save_message("assistant", full_response)
                else:
                    message_placeholder.warning("No response received from server.")
                    
            except Exception as e:
                message_placeholder.error(f"Error: {str(e)}")
        
        st.rerun()
