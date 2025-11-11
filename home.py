import pandas as pd
from google import genai
from google.genai import types
import json
from dotenv import load_dotenv
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import streamlit as st

load_dotenv()
client = genai.Client()

class AssertionEvaluator:
    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.evaluation_results = []

    # Read the main sheet and locate the assertions table
    def read_assertions(self, sheet_name: str = "Main") -> pd.DataFrame:
        df = pd.read_excel(self.excel_path, sheet_name=sheet_name, header=None)
        
        for row_idx, row in df.iterrows():
            if "Assertion" in row.values:
                col_idx = row[row == "Assertion"].index[0]
                break
        
        sliced = df.iloc[row_idx:, col_idx:]
        sliced.columns = sliced.iloc[0]
        return sliced.iloc[1:].reset_index(drop=True)

    # Extract assertions and testing procedures in readable format
    def extract_assertions(self, sheet_name: str = "Main") -> list[dict]:
        df = self.read_assertions(sheet_name)
        current = None
        details = []
        all_assertions = []

        for _, row in df.iterrows():
            value = row.get("Assertion")
            if pd.notna(value):
                if current:
                    all_assertions.append({'assertion': current, 'procedures': details.copy()})
                current = value
                details = [{'procedure': row.get('Testing procedures performed'), 'link': row.get("Link")}]
            elif current:
                details.append({'procedure': row.get('Testing procedures performed'), 'link': row.get("Link")})
        
        if current:
            all_assertions.append({'assertion': current, 'procedures': details})

        return all_assertions
    
    # Read individual sheets based on links provided in the main sheet
    def read_linked_sheet(self, link: str) -> dict:
        if pd.isna(link):
            return {'error': 'No link provided'}
        
        try:
            sheet_name = str(link).strip().replace("'!A1", "").replace("!A1", "")
            df = pd.read_excel(self.excel_path, sheet_name=sheet_name, header=None)
            return {
                'sheet_name': sheet_name,
                'raw_data': df.values.tolist(),
                'shape': f"{df.shape[0]} rows x {df.shape[1]} columns"
            }
        except Exception as e:
            return {'error': f'Error reading sheet: {str(e)}'}
    
    # Prepare context for the LLM
    def prepare_context(self, assertion: str, procedures: list[dict]) -> str:
        context = f"Evaluate: {assertion}\n\nTesting Procedures and Related Data:\n\n"
        
        for i, proc in enumerate(procedures, 1):
            context += f"Procedure {i}\nDescription: {proc['procedure']}\n\n"
            
            if pd.notna(proc['link']):
                sheet_data = self.read_linked_sheet(proc['link'])
                if 'error' not in sheet_data:
                    context += f"Linked Sheet: {sheet_data['sheet_name']}\n"
                    context += f"Dimensions: {sheet_data['shape']}\n"
                    context += f"Data:\n{json.dumps(sheet_data['raw_data'], indent=2, default=str)}\n\n"
                else:
                    context += f"Error: {sheet_data['error']}\n\n"
            context += "---\n\n"
        
        return context
    
    # Evaluate a particular assertion using Gemini
    def evaluate_assertion(self, assertion: str, procedures: list[dict]) -> str:
        context = self.prepare_context(assertion, procedures)
        
        prompt = f"""{context}

You are performing a first-level technical review of an audit workpaper. Your task is to critically evaluate the workpaper for technical accuracy, logical consistency, and documentation quality, applying professional audit judgment.

Objectives:
1. Mathematical Accuracy: Verify calculations and footings
2. Cross-Sheet Tie-Outs: Check figures agree across sheets
3. Logical Consistency: Assess if procedures support the conclusion
4. Documentation Quality: Check for clarity and completeness
5. Materiality: Assume 1% of net income threshold if not defined

Respond in JSON format:
{{
  "verdict": "TRUE" | "FALSE" | "PARTIALLY_TRUE" | "INSUFFICIENT_DATA",
  "confidence": 0-100,
  "reasoning": "Detailed explanation of your evaluation and rationale.",
  "key_findings": ["Main findings that influenced your conclusion."],
  "discrepancies": ["List of issues or inconsistencies found, leave empty if none."],
  "recommendations": ["Actionable suggestions to correct or improve the workpaper."]
}}
"""
        
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    thinking_config=types.ThinkingConfig(thinking_budget=-1)
                )
            )
            return response.text.strip()
        except Exception as e:
            return json.dumps({'verdict': 'ERROR', 'confidence': 0, 'reasoning': f'LLM evaluation error: {str(e)}'})

    # Parse the JSON response from the LLM
    def parse_json_result(self, result_text: str) -> dict:
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            if '```json' in result_text:
                start = result_text.find('```json') + 7
                end = result_text.find('```', start)
                return json.loads(result_text[start:end].strip())
            elif '```' in result_text:
                start = result_text.find('```') + 3
                end = result_text.find('```', start)
                return json.loads(result_text[start:end].strip())
            raise

    # Generate PDF report from evaluation results
    def generate_pdf_report(self, output_filename: str = None) -> tuple:
        if not self.evaluation_results:
            return None, None

        if output_filename is None:
            output_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        doc = SimpleDocTemplate(output_filename, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("Evaluation Report", styles["Title"]))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        for idx, result in enumerate(self.evaluation_results, 1):
            parsed = result.get("parsed_result", {})
            verdict = parsed.get("verdict", "UNKNOWN")
            confidence = parsed.get("confidence", 0)
            reasoning = parsed.get("reasoning", "N/A")
            elements.append(Paragraph(str(result.get("assertion", "")), styles["Heading2"]))
            elements.append(Paragraph(f"Verdict: {verdict} (Confidence: {confidence}%)", styles["Heading3"]))
            elements.append(Paragraph(f"Reasoning: {reasoning}", styles["Normal"]))

            for section in ["key_findings", "discrepancies", "recommendations"]:
                items = parsed.get(section, [])
                if items:
                    elements.append(Paragraph(section.replace("_", " ").title() + ":", styles["Heading4"]))
                    for item in items:
                        elements.append(Paragraph(f" {item}", styles["Normal"]))
            
            if idx < len(self.evaluation_results):
                elements.append(PageBreak())

        doc.build(elements)
        
        with open(output_filename, "rb") as f:
            pdf_bytes = f.read()
        
        return output_filename, pdf_bytes

    def evaluate_all(self, sheet_name: str = 'Main', progress_callback=None) -> int:
        """Evaluate all assertions in the workbook"""
        assertions = self.extract_assertions(sheet_name)
        self.evaluation_results = []
        
        for i, block in enumerate(assertions, 1):
            if progress_callback:
                progress_callback(i, len(assertions))
            
            result_text = self.evaluate_assertion(block['assertion'], block['procedures'])
            
            try:
                parsed_result = self.parse_json_result(result_text)
            except Exception as e:
                parsed_result = {
                    'verdict': 'ERROR', 
                    'confidence': 0, 
                    'reasoning': f'Parse error: {str(e)}', 
                    'key_findings': [], 
                    'discrepancies': [], 
                    'recommendations': []
                }
            
            self.evaluation_results.append({
                'assertion': block['assertion'],
                'procedures': block['procedures'],
                'raw_result': result_text,
                'parsed_result': parsed_result
            })
        
        return len(assertions)

st.set_page_config(page_title="Garuda")
st.title("Garuda")
uploaded_file = st.file_uploader("Choose an Excel file", type=['xlsx', 'xls'])
if uploaded_file:
    with open("temp_workbook.xlsx", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    if st.button("Evaluate", type="primary"):
        evaluator = AssertionEvaluator("temp_workbook.xlsx")
        
        progress_bar = st.progress(0)
        status = st.empty()
        
        def update_progress(current, total):
            progress_bar.progress(current / total)
            status.text(f"Processing {current}/{total} ...")
        
        with st.spinner("Evaluating..."):
            total = evaluator.evaluate_all("Main", update_progress)
        
        status.success(f"Complete!")
        
        with st.spinner("Generating PDF..."):
            filename, pdf_bytes = evaluator.generate_pdf_report()
        
        if pdf_bytes:
            st.download_button(
                label="Download PDF Report",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                type="primary"
            )