"""Tools page with separate tool access."""
import streamlit as st
from src.utils.api_client import api_client
import json

def show_tools():
    """Display tools interface."""
    st.title("🛠️ Tools")
    
    # Tool selection
    tool = st.radio(
        "Select a tool:",
        ["DSM-5 Search", "DSM-5 Hybrid Search", "Hospital Query"],
        horizontal=True
    )
    
    st.divider()
    
    if tool == "DSM-5 Search":
        show_dsm5_search()
    elif tool == "DSM-5 Hybrid Search":
        show_dsm5_hybrid()
    elif tool == "Hospital Query":
        show_hospital_query()

def show_dsm5_search():
    """DSM-5 Search tool."""
    st.subheader("Search DSM-5 Diagnostic Criteria")
    
    query = st.text_input("Enter your search query", placeholder="e.g., depression, anxiety, PTSD...")
    
    if st.button("Search", key="dsm5_search_btn"):
        if not query.strip():
            st.warning("Please enter a search query")
            return
            
        with st.spinner("Searching..."):
            response = api_client.dsm5_search(query)
            
            if "error" in response:
                st.error(f"Error: {response['error']}")
            else:
                results_count = response.get('results_count', 0)
                st.success(f"✅ Found {results_count} results")
                
                with st.container():
                    st.markdown(response.get("response", "No results found"))
                
                # Show stats
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Results Count", results_count)
                with col2:
                    st.metric("Query Length", len(query))

def show_dsm5_hybrid():
    """DSM-5 Hybrid Search tool."""
    st.subheader("DSM-5 Hybrid Search (Keyword + Semantic)")
    
    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("Enter your search query", placeholder="e.g., major depressive episode...")
    with col2:
        top_k = st.number_input("Results to retrieve", min_value=1, max_value=20, value=5)
    
    if st.button("Search", key="dsm5_hybrid_btn"):
        if not query.strip():
            st.warning("Please enter a search query")
            return
            
        with st.spinner("Performing hybrid search..."):
            response = api_client.dsm5_hybrid_search(query, top_k)
            
            if "error" in response:
                st.error(f"Error: {response['error']}")
            else:
                results_count = response.get('results_count', 0)
                st.success(f"✅ Found {results_count} results")
                
                with st.container():
                    st.markdown(response.get("response", "No results found"))
                
                # Show stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Results Count", results_count)
                with col2:
                    st.metric("Top-K Setting", top_k)
                with col3:
                    st.metric("Query Length", len(query))

def show_hospital_query():
    """Hospital Query tool using Neo4j."""
    st.subheader("Query Hospital Data")
    
    query = st.text_area(
        "Enter your question (natural language or Cypher query)",
        placeholder="e.g., Find patients with diabetes diagnosed in 2023...",
        height=100
    )
    
    if st.button("Execute Query", key="hospital_query_btn"):
        if not query.strip():
            st.warning("Please enter a query")
            return
            
        with st.spinner("Executing query..."):
            response = api_client.cypher_query(query)
            
            if "error" in response:
                st.error(f"Error: {response['error']}")
            else:
                col1, col2 = st.columns([1, 1], gap="large")
                
                with col1:
                    st.subheader("📊 Answer")
                    st.write(response.get("answer", "No answer available"))
                
                with col2:
                    st.subheader("🔍 Generated Cypher")
                    cypher_code = response.get("cypher", "")
                    if cypher_code:
                        st.code(cypher_code, language="cypher")
                    else:
                        st.info("No Cypher generated")
                
                st.divider()
                st.info(f"Query length: {len(query)} characters")
