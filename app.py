import streamlit as st
from gemini_model import create_gemini_client, generate_content_with_fallback, get_response_text
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
if "last_model" not in st.session_state:
    st.session_state.last_model = None

# --- 2. LOGIC ---
def _parse_json_response(response):
    text = get_response_text(response)
    cleaned = text.replace(chr(96) * 3 + "json", "").replace(chr(96) * 3, "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Be tolerant of a short explanatory prefix/suffix around the JSON.
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def extract_receipt_data(image, api_key):
    client = create_gemini_client(api_key)

    prompt = """
    Analyze this receipt image.
    Step 1: Extract the summary details (Date, Vendor, Tax, Currency, Total Amount).
    Step 2: Extract every single line item (Product Name, Price).

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

    Return JSON only. Use null for values that are not visible.
    """

    try:
        response, model_name = generate_content_with_fallback(
            client, [prompt, image], api_key
        )
        data = _parse_json_response(response)
        if not isinstance(data, dict):
            raise ValueError("Gemini returned a JSON value instead of an object.")
        if not isinstance(data.get("summary", {}), dict):
            raise ValueError("Gemini returned an invalid receipt summary.")
        if not isinstance(data.get("items", []), list):
            raise ValueError("Gemini returned invalid receipt items.")
        return data, model_name
    except Exception as error:
        return {"error": str(error)}


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
    file_id = getattr(uploaded_file, "file_id", None) or f"{uploaded_file.name}:{uploaded_file.size}"
    
    col1, col2 = st.columns([1, 2])
    with col1:
        image = Image.open(uploaded_file)
        st.image(image, caption="Receipt", use_container_width=True)
        
        btn_disabled = file_id in st.session_state.processed_files
        btn_label = "✅ Scanned" if btn_disabled else "🚀 Scan Items"
        
        if st.button(btn_label, type="primary", disabled=btn_disabled):
            with st.spinner("Analyzing receipt..."):
                raw_data = extract_receipt_data(image, api_key)
                if isinstance(raw_data, tuple):
                    raw_data, model_name = raw_data
                    st.session_state.last_model = model_name
                
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
                    try:
                        tax_amount = float(tax_val or 0)
                    except (TypeError, ValueError):
                        tax_amount = 0.0
                    if tax_amount > 0:
                        tax_row = {
                            "date": summary.get("date"),
                            "vendor": summary.get("vendor"),
                            "item_name": "Tax",
                            "price": tax_amount,
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
if st.session_state.last_model:
    st.caption(f"Last model used: {st.session_state.last_model}")

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
    st.session_state.expense_data = edited_df.to_dict("records")
    
    csv = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download CSV", csv, "receipt_complete.csv", "text/csv", type="primary")

else:
    if uploaded_file and not api_key:
        st.warning("Add a Gemini API key in the sidebar to scan this receipt.")
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
