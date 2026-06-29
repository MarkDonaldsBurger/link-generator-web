import streamlit as st
import gspread
import uuid
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Link Generator & Status Tracker", layout="wide")

# 1. Connection
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = Credentials.from_service_account_info(st.secrets["gservice_account"], scopes=scope)
        return gspread.authorize(creds)
    except: return None

def get_sheet():
    client = get_gspread_client()
    if client: return client.open_by_url("https://docs.google.com/spreadsheets/d/1J8WLEW2ZI57iUDNU4zzGoN1jI7MW_F06EX2mLN6fZhE/edit?usp=sharing").sheet1
    return None

# 2. Database
def load_tokens_from_sheet(sheet):
    try:
        records = sheet.get_all_records()
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        df.columns = df.columns.str.strip()
        
        # Build the full clickable/copyable URL
        base_app_url = "https://dynamiclinkgeneratorpy-jvrqcasnbsduy6hwwmco58.streamlit.app/"
        if "Token" in df.columns:
            df["Full Generated Link"] = base_app_url + "?token=" + df["Token"].astype(str)
        
        # KEY CHANGE: 
        # Set the display order. "Status" is first, ensuring it appears on the far left.
        # This keeps the underlying Google Sheet format (Token, Status, etc.) untouched.
        desired_order = ["Status", "Token", "Date Issued", "Ticket No.", "Form URL", "Type", "Full Generated Link"]
        
        # Keep only columns that exist in the dataframe
        current_order = [col for col in desired_order if col in df.columns]
        df = df[current_order]
        
        return df
    except Exception as e:
        st.error(f"Error reading datastore: {e}")
        return None

def update_token_status(sheet, token, new_status):
    all_rows = sheet.get_all_values()
    for idx, row in enumerate(all_rows):
        if row and row[0] == token:
            sheet.update_cell(idx + 1, 1, new_status)
            return True
    return False

# 3. UI
sheet = get_sheet()
if sheet:
    st.title("🔗 Management Console")
    df_tokens = load_tokens_from_sheet(sheet)
    
    col_left, col_right = st.columns([1, 3])
    
    with col_left:
        st.subheader("Generate New Link")
        t_no = st.text_input("Ticket No.")
        status = st.selectbox("Status", ["On hold", "Active", "Terminated", "Used"])
        
        c_int, c_ext = st.columns(2)
        if c_int.button("Generate Internal", use_container_width=True):
            sheet.append_row([status, t_no, "INTERNAL", datetime.now().strftime("%Y-%m-%d"), str(uuid.uuid4()), "https://forms.office.com/r/5s3GA7Df0T"])
            st.rerun()
        if c_ext.button("Generate External", use_container_width=True):
            sheet.append_row([status, t_no, "EXTERNAL", datetime.now().strftime("%Y-%m-%d"), str(uuid.uuid4()), "https://forms.office.com/r/KchEak7FWA"])
            st.rerun()

    with col_right:
        st.subheader("Active Token Registry")
        f1, f2 = st.columns(2)
        with f1: search = st.text_input("🔍 Search by Ticket No.")
        with f2: type_filter = st.selectbox("📂 Filter by Type", ["All", "INTERNAL", "EXTERNAL"])
        
        df_display = df_tokens
        if search: df_display = df_display[df_display["Ticket No."].astype(str).str.contains(search, case=False)]
        if type_filter != "All": df_display = df_display[df_display["Type"] == type_filter]
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        st.markdown("#### ✏️ Quick Status Update")
        u1, u2, u3, u4, u5 = st.columns([1.5, 2, 1.2, 1.2, 1.2])
        
        with u1: link_type = st.selectbox("Type", ["INTERNAL", "EXTERNAL"], key="up_type")
        with u2: 
            opts = df_tokens[df_tokens["Type"] == link_type]["Ticket No."].unique().tolist()
            sel = st.selectbox("Select Ticket", [""] + opts, key="up_ticket")
        
        current_status_val = "N/A"
        if sel:
            match = df_tokens[(df_tokens["Ticket No."].astype(str) == str(sel)) & (df_tokens["Type"] == link_type)]
            if not match.empty: current_status_val = match.iloc[0]["Status"]
            
        with u3: st.text_input("Current Status", value=current_status_val, disabled=True)
        with u4: n_status = st.selectbox("New Status", ["On hold", "Active", "Terminated", "Used"], key="up_status")
        
        with u5:
            st.markdown("<br>", unsafe_allow_html=True) # Manual spacing to force alignment
            b_up, b_can = st.columns(2)
            if b_up.button("Update", use_container_width=True):
                match = df_tokens[(df_tokens["Ticket No."].astype(str) == str(sel)) & (df_tokens["Type"] == link_type)]
                if not match.empty:
                    update_token_status(sheet, match.iloc[0]["Token"], n_status)
                    st.rerun()
            if b_can.button("Cancel", use_container_width=True):
                for key in ['up_type', 'up_ticket', 'up_status']:
                    if key in st.session_state: del st.session_state[key]
                st.rerun()
