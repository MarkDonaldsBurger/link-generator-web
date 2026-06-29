import streamlit as st
import gspread
import uuid
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# Set up browser page configuration
st.set_page_config(page_title="Link Generator & Status Tracker", layout="wide")

# 1. Authenticate with Google Sheets using Streamlit Secrets
@st.cache_resource
def get_gspread_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        creds_info = st.secrets["gservice_account"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Failed to authenticate with Google: {e}")
        return None

def get_sheet():
    client_obj = get_gspread_client()
    if client_obj:
        sheet_url = "https://docs.google.com/spreadsheets/d/1J8WLEW2ZI57iUDNU4zzGoN1jI7MW_F06EX2mLN6fZhE/edit?usp=sharing"
        return client_obj.open_by_url(sheet_url).sheet1
    return None

# 2. Database Core Operations
def load_tokens_from_sheet(sheet):
    try:
        records = sheet.get_all_records()
        if not records: return pd.DataFrame()
        
        df = pd.DataFrame(records)
        df.columns = df.columns.str.strip()
        
        # Build URL
        base_app_url = "https://dynamiclinkgeneratorpy-jvrqcasnbsduy6hwwmco58.streamlit.app/"
        if "Token" in df.columns:
            df["Full Generated Link"] = base_app_url + "?token=" + df["Token"].astype(str)
        
        # COLUMN ORDER: Status first, then Ticket No.
        desired_order = ["Status", "Ticket No.", "Type", "Date Issued", "Token", "Full Generated Link", "Form URL"]
        df = df[[col for col in desired_order if col in df.columns]]
        return df
    except Exception as e:
        st.error(f"Error reading datastore: {e}")
        return None

def update_token_status(sheet, token, new_status):
    try:
        all_rows = sheet.get_all_values()
        for idx, row in enumerate(all_rows):
            if row and row[0] == token:
                sheet.update_cell(idx + 1, 1, new_status) # Assuming Status is Col 1
                return True
        return False
    except Exception as e:
        st.error(f"Failed to update status: {e}")
        return False

# 3. Runtime Interface
sheet = get_sheet()

if sheet:
    query_params = st.query_params
    token_param = query_params.get("token")

    if token_param:
        st.title("🛡️ Internal Verification Gateway")
        user_email = st.text_input("Enter @dti.gov.ph email:").strip().lower()
        if user_email and user_email.endswith("@dti.gov.ph"):
            df_tokens = load_tokens_from_sheet(sheet)
            matched = df_tokens[df_tokens["Token"] == token_param]
            if not matched.empty and matched.iloc[0]["Status"] == "Active":
                st.success("Verified!")
                st.link_button("👉 Open Workspace", url=matched.iloc[0]["Form URL"], type="primary")
    else:
        st.title("🔗 Dynamic Link Management Console")
        df_tokens = load_tokens_from_sheet(sheet)
        
        # Display Table
        st.dataframe(df_tokens, use_container_width=True, hide_index=True)

        # Quick Status Update Tool
        st.divider()
        st.markdown("#### ✏️ Quick Status Update")
        u1, u2, u3, u4 = st.columns([1.5, 2, 1.5, 1])
        
        with u1: type_choice = st.selectbox("Link Type", ["INTERNAL", "EXTERNAL"], key="up_type")
        with u2: 
            opts = df_tokens[df_tokens["Type"] == type_choice]["Ticket No."].unique().tolist()
            selected_ticket = st.selectbox("Select/Type Ticket", [""] + opts, key="up_ticket")
        with u3: new_status = st.selectbox("New Status", ["On hold", "Active", "Terminated", "Used"], key="up_status")
        with u4:
            st.write("") 
            if st.button("Update"):
                match = df_tokens[(df_tokens["Ticket No."] == selected_ticket) & (df_tokens["Type"] == type_choice)]
                if not match.empty:
                    if update_token_status(sheet, match.iloc[0]["Token"], new_status):
                        st.success(f"Updated {selected_ticket} to {new_status}!")
                        st.cache_data.clear()
                        st.rerun()
