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
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        df.columns = df.columns.str.strip()
        
        if "Ticket No." not in df.columns:
            if "Ticket Number" in df.columns:
                df = df.rename(columns={"Ticket Number": "Ticket No."})
            elif "Ticket_No" in df.columns:
                df = df.rename(columns={"Ticket_No": "Ticket No."})
        
        base_app_url = "https://dynamiclinkgeneratorpy-jvrqcasnbsduy6hwwmco58.streamlit.app/"
        if "Token" in df.columns:
            df["Full Generated Link"] = base_app_url + "?token=" + df["Token"].astype(str)
        
        desired_order = ["Ticket No.", "Type", "Date Issued", "Token", "Full Generated Link", "Form URL", "Status"]
        current_order = [col for col in desired_order if col in df.columns]
        df = df[current_order]
        
        return df
    except Exception as e:
        st.error(f"Error reading datastore: {e}")
        return None

def generate_client_link(sheet, client_name, status, link_type):
    try:
        token = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        form_url = "https://forms.office.com/r/5s3GA7Df0T" if link_type == "INTERNAL" else "https://forms.office.com/r/KchEak7FWA"
        
        sheet.append_row([token, status, timestamp, client_name, form_url, link_type])
        gatekeeper_url = f"https://dynamiclinkgeneratorpy-jvrqcasnbsduy6hwwmco58.streamlit.app/?token={token}"
        return token, gatekeeper_url
    except Exception as e:
        return None, str(e)

def update_token_status(sheet, token, new_status):
    try:
        all_rows = sheet.get_all_values()
        for idx, row in enumerate(all_rows):
            if row and len(row) > 0 and row[0] == token:
                sheet.update_cell(idx + 1, 2, new_status) 
                return True
        return False
    except Exception as e:
        st.error(f"Failed to update status: {e}")
        return False

@st.dialog("🚀 Link Successfully Generated!")
def show_success_popup(url, link_type, ticket):
    st.success(f"Successfully created a new **{link_type}** tracking link.")
    st.write(f"**Ticket Ref:** {ticket}")
    st.text_area("Copy Dynamic Link:", value=url, height=80)
    
    if st.button("Close & Refresh Dashboard", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 3. Runtime Routing & Web Interface
sheet = get_sheet()

if sheet:
    query_params = st.query_params
    token_param = query_params.get("token")

    if token_param:
        # GATEKEEPER VIEW
        st.title("🛡️ Internal Verification Gateway")
        user_email = st.text_input("Enter your official office email address:", placeholder="username@dti.gov.ph").strip().lower()

        if user_email:
            if not user_email.endswith("@dti.gov.ph"):
                st.error("Access Denied: You must use an authorized organizational email address (@dti.gov.ph).")
            else:
                df_tokens = load_tokens_from_sheet(sheet)
                matched_row = df_tokens[df_tokens["Token"] == token_param] if df_tokens is not None else pd.DataFrame()
                
                if matched_row.empty:
                    st.error("Invalid Link Sequence.")
                else:
                    status = matched_row.iloc[0]["Status"]
                    form_url = matched_row.iloc[0]["Form URL"]
                    
                    if status != "Active":
                        st.error(f"Access Denied: Link is {status}.")
                    else:
                        st.success("Verification successful! Access granted.")
                        st.markdown(
                            f"""<a href="{form_url}" target="_blank" style="display: block; width: 100%; background-color: #ff4b4b; color: white; text-align: center; padding: 1rem; border-radius: 0.5rem; text-decoration: none; font-weight: bold;">
                            👉 Open Microsoft Form Workspace</a>""", unsafe_allow_html=True
                        )
    else:
        # CONSOLE VIEW
        st.title("🔗 Dynamic Link Generator & Management Console")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Generate New Request Link")
            ticket_no = st.text_input("Ticket No. / Identifier")
            initial_status = st.selectbox("Initial Status", ["On hold", "Active", "Terminated", "Used"])
            
            b1, b2 = st.columns(2)
            if b1.button("Gen. External", use_container_width=True):
                token, url = generate_client_link(sheet, ticket_no, initial_status, "EXTERNAL")
                if token: show_success_popup(url, "EXTERNAL", ticket_no)
            if b2.button("Gen. Internal", use_container_width=True):
                token, url = generate_client_link(sheet, ticket_no, initial_status, "INTERNAL")
                if token: show_success_popup(url, "INTERNAL", ticket_no)

        with col2:
            st.subheader("Real-Time Token Sync View")
            if st.button("🔄 Refresh Data"): st.cache_data.clear(); st.rerun()
            df_tokens = load_tokens_from_sheet(sheet)
            st.dataframe(df_tokens, use_container_width=True, hide_index=True)

            # REFINED QUICK STATUS UPDATE TOOL
            st.divider()
            st.markdown("#### ✏️ Quick Status Update")
            
            type_select = st.selectbox("1. Filter by Link Type", options=["INTERNAL", "EXTERNAL"], key="upd_type")
            type_filtered_df = df_tokens[df_tokens["Type"] == type_select]
            
            selected_ticket = st.selectbox("2. Select or Type Ticket Number", options=["-- Select --"] + type_filtered_df["Ticket No."].unique().tolist(), key="upd_ticket")
            
            if selected_ticket != "-- Select --":
                row = type_filtered_df[type_filtered_df["Ticket No."] == selected_ticket].iloc[0]
                new_status = st.selectbox("3. Select New Status", options=["On hold", "Active", "Terminated", "Used"], index=["On hold", "Active", "Terminated", "Used"].index(row["Status"]))
                
                c1, c2 = st.columns(2)
                if c1.button("💾 Confirm Update", type="primary", use_container_width=True):
                    if update_token_status(sheet, row["Token"], new_status):
                        st.toast("Updated successfully!", icon="✅"); st.cache_data.clear(); st.rerun()
                if c2.button("🔄 Refresh Page", use_container_width=True): st.cache_data.clear(); st.rerun()
