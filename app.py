import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import os

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Receipt Ripper V3", page_icon="🧾", layout="centered")

api_key = None
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    elif os.getenv("GEMINI_API_KEY"):
        api_key = os.getenv("GEMINI_API_KEY")
except:
    pass

# Initialize Session State
if "expense_data" not in st.session_state:
    st.session_state.expense_data = []
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

# --- 2. LOGIC ---
def extract_receipt_data(image, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    # PROMPT UPDATE: Requesting "total" in summary explicitly
    prompt = """
    Analyze this receipt image. 
    Step 1: Extract the "summary" details (Date, Vendor, Tax, Currency, Total Amount).
    Step 2: Extract every single "line_item" (Product Name, Price).
    
    Return a valid JSON object with this exact structure:
    {
        "summary": {
            "date": "YYYY-MM-DD",
            "vendor": "Store Name",
            "currency": "USD",
            "tax": 0.00,
            "total": 0.00
        },
        "items": [
            {"name": "Item 1 Name", "price": 10.00, "category": "Food"},
            {"name": "Item 2 Name", "price": 5.50, "category": "Food"}
        ]
    }
    """
    
    try:
        response = model.generate_content([prompt, image])
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        return {"error": str(e)}

# --- 3. UI LAYOUT ---
st.title("🧾 Receipt Ripper V3")
st.markdown("Extracts Items + Tax + Final Total.")

with st.sidebar:
    st.header("⚙️ Controls")
    if api_key:
        st.success("✅ Connected")
    else:
        api_key = st.text_input("API Key", type="password")
    
    if st.button("🗑️ Clear All Data"):
        st.session_state.expense_data = []
        st.session_state.processed_files = set()
        st.rerun()

# Main Area
uploaded_file = st.file_uploader("Upload Receipt", type=["jpg", "png", "jpeg", "webp"])

if uploaded_file and api_key:
    file_id = uploaded_file.file_id
    
    col1, col2 = st.columns([1, 2])
    with col1:
        image = Image.open(uploaded_file)
        st.image(image, caption="Receipt", use_container_width=True)
        
        btn_disabled = file_id in st.session_state.processed_files
        btn_label = "✅ Scanned" if btn_disabled else "🚀 Scan Items"
        
        if st.button(btn_label, type="primary", disabled=btn_disabled):
            with st.spinner("Analyzing receipt..."):
                raw_data = extract_receipt_data(image, api_key)
                
                if "error" in raw_data:
                    st.error(f"Error: {raw_data['error']}")
                else:
                    summary = raw_data.get("summary", {})
                    items = raw_data.get("items", [])
                    
                    # 1. Add Line Items
                    for item in items:
                        flat_row = {
                            "date": summary.get("date"),
                            "vendor": summary.get("vendor"),
                            "item_name": item.get("name"),
                            "price": item.get("price"),
                            "currency": summary.get("currency"),
                            "category": item.get("category", "Other")
                        }
                        st.session_state.expense_data.append(flat_row)
                    
                    # 2. Add Tax Line (if > 0)
                    tax_val = summary.get("tax", 0)
                    if tax_val and float(tax_val) > 0:
                        tax_row = {
                            "date": summary.get("date"),
                            "vendor": summary.get("vendor"),
                            "item_name": "Tax",
                            "price": tax_val,
                            "currency": summary.get("currency"),
                            "category": "Tax"
                        }
                        st.session_state.expense_data.append(tax_row)

                    # 3. Add TOTAL Line
                    total_val = summary.get("total", 0)
                    total_row = {
                        "date": summary.get("date"),
                        "vendor": summary.get("vendor"),
                        "item_name": "*** TOTAL ***",
                        "price": total_val,
                        "currency": summary.get("currency"),
                        "category": "Total"
                    }
                    st.session_state.expense_data.append(total_row)
                    
                    st.session_state.processed_files.add(file_id)
                    st.rerun()

# --- 4. RESULTS TABLE ---
st.markdown("### 📊 Detailed Item Log")

if len(st.session_state.expense_data) > 0:
    df = pd.DataFrame(st.session_state.expense_data)
    
    # Date Fix
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "price": st.column_config.NumberColumn("Price", format="%.2f"),
            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "category": st.column_config.SelectboxColumn("Category", options=["Food", "Transport", "Office", "Utilities", "Tech", "Tax", "Total"])
        }
    )
    
    csv = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download CSV", csv, "receipt_complete.csv", "text/csv", type="primary")

else:
    st.info("Upload a receipt to generate the report.")

# Footer
def show_footer():
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; padding-top: 20px;">
            <a href="https://buymeacoffee.com/isamir" target="_blank">
                <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 50px !important;width: 180px !important;" >
            </a>
            <p style="margin-top: 15px; color: #aaa; font-size: 0.9em;">
                This tool is 100% free. If it saved you time, a coffee is always appreciated! ☕
            </p>
            <p style="color: #999; font-size: 0.8em;">
                Made by Ibrahim Samir | <a href="https://takea5.com" target="_blank" style="color: #999; text-decoration: none;">Takea5.com</a>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

# Call it at the ends
show_footer()
