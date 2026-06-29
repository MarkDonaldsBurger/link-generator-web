import streamlit as st
import gspread
import uuid
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Link Generator & Status Tracker", layout="wide")

# 1. Authentication & Sheet Connection
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

# 2. Database Operations
def load_tokens_from_sheet(sheet):
    records = sheet.get_all_records()
    if not records: return pd.DataFrame()
    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip()
    base_url = "https://dynamiclinkgeneratorpy-jvrqcasnbsduy6hwwmco58.streamlit.app/"
    if "Token" in df.columns: df["Full Generated Link"] = base_url + "?token=" + df["Token"].astype(str)
    order = ["Status", "Ticket No.", "Type", "Date Issued", "Token", "Full Generated Link", "Form URL"]
    return df[[c for c in order if c in df.columns]]

def update_token_status(sheet, token, new_status):
    all_rows = sheet.get_all_values()
    for idx, row in enumerate(all_rows):
        if row and row[0] == token:
            sheet.update_cell(idx + 1, 1, new_status)
            return True
    return False

# 3. Main Interface
sheet = get_sheet()
if sheet:
    st.title("🔗 Management Console")
    df_tokens = load_tokens_from_sheet(sheet)
    
    c1, c2 = st.columns([1, 3])
    
    with c1:
        st.subheader("Generate New Link")
        t_no = st.text_input("Ticket No.")
        status = st.selectbox("Status", ["On hold", "Active", "Terminated", "Used"])
        if st.button("Generate Internal"):
            sheet.append_row([status, t_no, "INTERNAL", datetime.now().strftime("%Y-%m-%d"), str(uuid.uuid4()), "https://forms.office.com/r/5s3GA7Df0T"])
            st.rerun()
        if st.button("Generate External"):
            sheet.append_row([status, t_no, "EXTERNAL", datetime.now().strftime("%Y-%m-%d"), str(uuid.uuid4()), "https://forms.office.com/r/KchEak7FWA"])
            st.rerun()

    with c2:
        st.subheader("Active Token Registry")
        # Filters
        f1, f2 = st.columns(2)
        with f1: search = st.text_input("🔍 Search by Ticket No.")
        with f2: type_filter = st.selectbox("📂 Filter by Type", ["All", "INTERNAL", "EXTERNAL"])
        
        display_df = df_tokens
        if search: display_df = display_df[display_df["Ticket No."].astype(str).str.contains(search, case=False)]
        if type_filter != "All": display_df = display_df[display_df["Type"] == type_filter]
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Status Update Tool
        st.markdown("#### ✏️ Quick Status Update")
        # Initialize session state for resets
        if 'up_type' not in st.session_state: st.session_state.up_type = "INTERNAL"
        if 'up_ticket' not in st.session_state: st.session_state.up_ticket = None

        u1, u2, u3, u4 = st.columns([1.5, 2, 1.5, 1.5])
        with u1: link_type = st.selectbox("Type", ["INTERNAL", "EXTERNAL"], key="up_type")
        with u2: 
            opts = df_tokens[df_tokens["Type"] == link_type]["Ticket No."].unique().tolist()
            sel = st.selectbox("Select Ticket", [""] + opts, key="up_ticket")
        with u3: n_status = st.selectbox("New Status", ["On hold", "Active", "Terminated", "Used"], key="up_status")
        with u4:
            st.write("")
            b1, b2 = st.columns(2)
            with b1:
                if st.button("Update"):
                    match = df_tokens[(df_tokens["Ticket No."].astype(str) == str(sel)) & (df_tokens["Type"] == link_type)]
                    if not match.empty:
                        update_token_status(sheet, match.iloc[0]["Token"], n_status)
                        st.success("Updated!")
                        st.rerun()
            with b2:
                if st.button("Cancel"):
                    # Use del to remove the keys instead of setting them to None
                    for key in ['up_type', 'up_ticket', 'up_status']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
