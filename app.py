import streamlit as st
import gspread
import uuid
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# Global Style for Precise Alignment
st.markdown("""
    <style>
    div[data-testid="column"]:nth-of-type(5) .stButton button { margin-top: 28px; }
    </style>
    """, unsafe_allow_html=True)

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
    records = sheet.get_all_records()
    if not records: return pd.DataFrame()
    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip()
    
    base_app_url = "https://dynamiclinkgeneratorpy-jvrqcasnbsduy6hwwmco58.streamlit.app/"
    if "Token" in df.columns:
        df["Full Generated Link"] = base_app_url + "?token=" + df["Token"].astype(str)
    
    # Precise ordering: Status first, then existing structure
    desired_order = ["Status", "Token", "Date Issued", "Ticket No.", "Form URL", "Type", "Full Generated Link"]
    df = df[[col for col in desired_order if col in df.columns]]
    return df

def update_token_status(sheet, token, new_status):
    all_rows = sheet.get_all_values()
    # Find row where Column 1 (Token) matches
    for idx, row in enumerate(all_rows):
        if row and row[0] == token:
            # Update Column 2 (Status)
            sheet.update_cell(idx + 1, 2, new_status)
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
        c1, c2 = st.columns(2)
        if c1.button("Generate Internal", use_container_width=True):
            sheet.append_row([str(uuid.uuid4()), status, datetime.now().strftime("%Y-%m-%d"), t_no, "https://forms.office.com/r/5s3GA7Df0T", "INTERNAL"])
            st.rerun()
        if c2.button("Generate External", use_container_width=True):
            sheet.append_row([str(uuid.uuid4()), status, datetime.now().strftime("%Y-%m-%d"), t_no, "https://forms.office.com/r/KchEak7FWA", "EXTERNAL"])
            st.rerun()

    with col_right:
        st.subheader("Active Token Registry")
        f1, f2 = st.columns(2)
        with f1: search = st.text_input("🔍 Search by Ticket No.")
        with f2: type_filter = st.selectbox("📂 Filter by Type", ["All", "INTERNAL", "EXTERNAL"])
        
        d_df = df_tokens
        if search: d_df = d_df[d_df["Ticket No."].astype(str).str.contains(search, case=False)]
        if type_filter != "All": d_df = d_df[d_df["Type"] == type_filter]
        
        st.dataframe(d_df, use_container_width=True, hide_index=True)
        
        st.markdown("#### ✏️ Quick Status Update")
        u1, u2, u3, u4, u5 = st.columns([1.5, 2, 1.2, 1.2, 1.5])
        
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
        
        with u5:
            b_up, b_can = st.columns(2)
            if b_up.button("Update", use_container_width=True):
                match = df_tokens[(df_tokens["Ticket No."].astype(str) == str(sel)) & (df_tokens["Type"] == link_type)]
                if not match.empty:
                    update_token_status(sheet, match.iloc[0]["Token"], n_status)
                    st.rerun()
            if b_can.button("Cancel", use_container_width=True):
                for k in ['up_type', 'up_ticket', 'up_status']:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()
