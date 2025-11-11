import streamlit as st
st.header("Information")

st.subheader("What is Garuda?")
st.write("""
Garuda is an AI-assisted work paper evaluation tool designed to analyze procedures followed in work papers.
It provides insights and suggestions to improve the quality and compliance of work papers.
""")

st.subheader("How do I use Garuda?")
st.write("""
1. Upload your work paper document in excel format.
2. Wait for Garuda to analyze the document.
3. Garuda will generate a PDF report with insights, nuances and suggestions that you can implement.
""")

st.subheader("What are the limitations for this tool?")
st.write("""
- It currently only supports documents in excel format
- While it may capture many nuances, it may not capture all nuances in the work paper.
- Complex judgements would still require human verification.
- Remember that this tool is mainly to assist an auditor make less mistakes in their work paper and not to replace human verification.
""")