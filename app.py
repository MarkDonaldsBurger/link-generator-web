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
    query_params = st.query_params
    token = query_params.get("token")

    if token:
        st.title("🛡️ Internal Verification")
        email = st.text_input("Office Email:")
        if email and email.endswith("@dti.gov.ph"):
            df = load_tokens_from_sheet(sheet)
            match = df[df["Token"] == token]
            if not match.empty and match.iloc[0]["Status"] == "Active":
                st.link_button("👉 Proceed to Workspace", url=match.iloc[0]["Form URL"], type="primary")
    else:
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
            # RESTORED: Filter Search
            search = st.text_input("🔍 Search by Ticket No.")
            display_df = df_tokens
            if search:
                display_df = display_df[display_df["Ticket No."].astype(str).str.contains(search, case=False)]
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # RESTORED: Status Update Tool
            st.markdown("#### ✏️ Quick Status Update")
            u1, u2, u3, u4 = st.columns([1.5, 2, 1.5, 1])
            with u1: link_type = st.selectbox("Type", ["INTERNAL", "EXTERNAL"], key="up_type")
            with u2: 
                opts = df_tokens[df_tokens["Type"] == link_type]["Ticket No."].unique().tolist()
                sel = st.selectbox("Select Ticket", [""] + opts)
            with u3: n_status = st.selectbox("New Status", ["On hold", "Active", "Terminated", "Used"])
            with u4:
                st.write("")
                if st.button("Update"):
                    match = df_tokens[(df_tokens["Ticket No."].astype(str) == str(sel)) & (df_tokens["Type"] == link_type)]
                    if not match.empty:
                        update_token_status(sheet, match.iloc[0]["Token"], n_status)
                        st.success("Updated!")
                        st.rerun()
