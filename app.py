import streamlit as st
import gspread
import uuid
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# 1. Page Config & Styling
st.set_page_config(page_title="Link Generator & Status Tracker", layout="wide")

st.markdown("""
    <style>
    /* Force buttons to align with the bottom of the input boxes */
    div.stButton > button { margin-top: 28px; width: 100%; }
    /* Style for the Update/Cancel button row specifically */
    .button-row { display: flex; gap: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 2. Connection Logic (Cached Resources)
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = Credentials.from_service_account_info(st.secrets["gservice_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

@st.cache_resource
def get_sheet():
    client = get_gspread_client()
    if client:
        return client.open_by_url("https://docs.google.com/spreadsheets/d/1J8WLEW2ZI57iUDNU4zzGoN1jI7MW_F06EX2mLN6fZhE/edit?usp=sharing").sheet1
    return None

# 3. Data Logic (Cached Data)
@st.cache_data(ttl=600)
def load_tokens_from_sheet():
    sheet = get_sheet()
    if not sheet: return pd.DataFrame()
    records = sheet.get_all_records()
    if not records: return pd.DataFrame()
    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip()
    
    base_app_url = "https://dynamiclinkgeneratorpy-jvrqcasnbsduy6hwwmco58.streamlit.app/"
    if "Token" in df.columns:
        df["Full Generated Link"] = base_app_url + "?token=" + df["Token"].astype(str)
    
    # Precise ordering
    desired_order = ["Status", "Token", "Date Issued", "Ticket No.", "Form URL", "Type", "Full Generated Link"]
    df = df[[col for col in desired_order if col in df.columns]]
    return df

def update_token_status(token, new_status):
    sheet = get_sheet()
    all_rows = sheet.get_all_values()
    for idx, row in enumerate(all_rows):
        if row and row[0] == token:
            sheet.update_cell(idx + 1, 2, new_status)
            return True
    return False

# 4. UI
st.title("🔗 Management Console")

# Refresh Logic
col_main1, col_main2 = st.columns([4, 1])
with col_main1: st.subheader("Active Token Registry")
with col_main2:
    if st.button("🔄 Refresh Table"):
        st.cache_data.clear()
        st.rerun()

# Load Data
df_tokens = load_tokens_from_sheet()

col_left, col_right = st.columns([1, 3])

with col_left:
    st.subheader("Generate New Link")
    t_no = st.text_input("Ticket No.")
    status = st.selectbox("Status", ["On hold", "Active", "Terminated", "Used"])
    c1, c2 = st.columns(2)
    
    def handle_generation(t_no, status, link_type, form_url):
        if not t_no:
            st.error("Please enter a Ticket No.")
            return
        
        # Check for duplicate
        is_duplicate = not df_tokens[(df_tokens["Ticket No."].astype(str) == str(t_no)) & (df_tokens["Type"] == link_type)].empty
        
        if is_duplicate:
            st.warning(f"A record for {link_type} for ticket {t_no} already exists!")
        else:
            token_val = str(uuid.uuid4())
            sheet = get_sheet()
            # STRICT ORDER: Token, Status, Date Issued, Ticket No., Form URL, Type
            sheet.append_row([token_val, status, datetime.now().strftime("%Y-%m-%d"), t_no, form_url, link_type])
            st.cache_data.clear()
            st.success(f"Successfully generated {link_type.lower()} link!")
            st.code(f"https://dynamiclinkgeneratorpy-jvrqcasnbsduy6hwwmco58.streamlit.app/?token={token_val}", language="text")
            if st.button("OK/Refresh"): st.rerun()

    if c1.button("Generate Internal", use_container_width=True):
        handle_generation(t_no, status, "INTERNAL", "https://forms.office.com/r/5s3GA7Df0T")
    if c2.button("Generate External", use_container_width=True):
        handle_generation(t_no, status, "EXTERNAL", "https://forms.office.com/r/KchEak7FWA")

with col_right:
    f1, f2 = st.columns(2)
    with f1: search = st.text_input("🔍 Search by Ticket No.")
    with f2: type_filter = st.selectbox("📂 Filter by Type", ["All", "INTERNAL", "EXTERNAL"])
    
    d_df = df_tokens
    if search: d_df = d_df[d_df["Ticket No."].astype(str).str.contains(search, case=False)]
    if type_filter != "All": d_df = d_df[d_df["Type"] == type_filter]
    
    st.dataframe(d_df, use_container_width=True, hide_index=True)
    
    st.markdown("#### ✏️ Quick Status Update")
    u1, u2, u3, u4 = st.columns([1.5, 2, 1.2, 1.2])
    
    with u1: link_type = st.selectbox("Type", ["INTERNAL", "EXTERNAL"], key="up_type")
    with u2: 
        opts = df_tokens[df_tokens["Type"] == link_type]["Ticket No."].unique().tolist()
        sel = st.selectbox("Select Ticket", [""] + opts, key="up_ticket")
    
    c_status = "N/A"
    if sel:
        match = df_tokens[(df_tokens["Ticket No."].astype(str) == str(sel)) & (df_tokens["Type"] == link_type)]
        if not match.empty: c_status = match.iloc[0]["Status"]
        
    with u3: st.text_input("Current Status", value=c_status, disabled=True)
    with u4: n_status = st.selectbox("New Status", ["On hold", "Active", "Terminated", "Used"], key="up_status")
    
    # Aligned Buttons
    b_col1, b_col2 = st.columns([1, 1])
    if b_col1.button("Update", use_container_width=True):
        match = df_tokens[(df_tokens["Ticket No."].astype(str) == str(sel)) & (df_tokens["Type"] == link_type)]
        if not match.empty:
            update_token_status(match.iloc[0]["Token"], n_status)
            st.cache_data.clear()
            st.rerun()
    if b_col2.button("Cancel", use_container_width=True):
        for k in ['up_type', 'up_ticket', 'up_status']:
            if k in st.session_state: del st.session_state[k]
        st.rerun()
