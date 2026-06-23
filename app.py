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
        # Pulls service account credentials directly from Streamlit cloud configuration
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

# 2. Database Core Operations (Synced Cloud Actions)
def load_tokens_from_sheet(sheet):
    try:
        records = sheet.get_all_records()
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        
        # CLEANUP: Strip whitespace from column names to prevent KeyErrors
        df.columns = df.columns.str.strip()
        
        # Fallback if the sheet column is named differently
        if "Ticket No." not in df.columns:
            if "Ticket Number" in df.columns:
                df = df.rename(columns={"Ticket Number": "Ticket No."})
            elif "Ticket_No" in df.columns:
                df = df.rename(columns={"Ticket_No": "Ticket No."})
        
        # Build the full clickable/copyable URL column dynamically
        base_app_url = "https://dynamiclinkgeneratorpy-jvrqcasnbsduy6hwwmco58.streamlit.app/"
        if "Token" in df.columns:
            df["Full Generated Link"] = base_app_url + "?token=" + df["Token"].astype(str)
        
        # Reorder columns so the Full Link is easily visible
        desired_order = ["Token", "Status", "Date Issued", "Ticket No.", "Full Generated Link", "Form URL", "Type"]
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
        
        # Append immediately to the cloud sheet (Syncs instantly for all web users)
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
                sheet.update_cell(idx + 1, 2, new_status) # Updates Column B (Status)
                return True
        return False
    except Exception as e:
        st.error(f"Failed to update status: {e}")
        return False

# 3. Streamlit Web Interface Construction
sheet = get_sheet()

if sheet:
    st.title("🔗 Dynamic Link Generator & Management Console")
    
    # Create two primary columns (Left Input Panel, Right Tracker Data Panel)
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Generate New Request Link")
        ticket_no = st.text_input("Ticket No. / Identifier", placeholder="Enter unique ID...")
        initial_status = st.selectbox("Initial Status", ["On hold", "Active", "Terminated", "Used"])
        
        btn_ext, btn_int = st.columns(2)
        with btn_ext:
            if st.button("Generate External Link", use_container_width=True):
                if ticket_no.strip():
                    # 1. Pull current sheet data to look for duplicate tickets
                    current_df = load_tokens_from_sheet(sheet)
                    
                    # 2. Check if this ticket already has an EXTERNAL record
                    duplicate_exists = False
                    if current_df is not None and not current_df.empty:
                        duplicate_exists = not current_df[
                            (current_df["Ticket No."].astype(str) == str(ticket_no.strip())) & 
                            (current_df["Type"] == "EXTERNAL")
                        ].empty
                    
                    if duplicate_exists:
                        st.error(f"Validation Error: Ticket No. '{ticket_no.strip()}' already has an active EXTERNAL link.")
                    else:
                        # Proceed with generation if clear
                        with st.spinner("Generating External Link..."):
                            token, url = generate_client_link(sheet, ticket_no.strip(), initial_status, "EXTERNAL")
                            if token:
                                st.success("Successfully generated and synced!")
                                st.text_area("Generated URL (Copy below):", value=url, height=70)
                                st.cache_data.clear() # Clear view cache to refresh table data
                                st.rerun()
                else:
                    st.warning("Please fill in the Ticket Number field.")
                    
        with btn_int:
            if st.button("Generate Internal Link", use_container_width=True):
                if ticket_no.strip():
                    # 1. Pull current sheet data to look for duplicate tickets
                    current_df = load_tokens_from_sheet(sheet)
                    
                    # 2. Check if this ticket already has an INTERNAL record
                    duplicate_exists = False
                    if current_df is not None and not current_df.empty:
                        duplicate_exists = not current_df[
                            (current_df["Ticket No."].astype(str) == str(ticket_no.strip())) & 
                            (current_df["Type"] == "INTERNAL")
                        ].empty
                    
                    if duplicate_exists:
                        st.error(f"Validation Error: Ticket No. '{ticket_no.strip()}' already has an active INTERNAL link.")
                    else:
                        # Proceed with generation if clear
                        with st.spinner("Generating Internal Link..."):
                            token, url = generate_client_link(sheet, ticket_no.strip(), initial_status, "INTERNAL")
                            if token:
                                st.success("Successfully generated and synced!")
                                st.text_area("Generated URL (Copy below):", value=url, height=70)
                                st.cache_data.clear()
                                st.rerun()
                else:
                    st.warning("Please fill in the Ticket Number field.")

    with col2:
        st.subheader("Real-Time Token Sync View")
        
        if st.button("🔄 Refresh Shared Sheet Data"):
            st.cache_data.clear()
            st.rerun()
            
        df_tokens = load_tokens_from_sheet(sheet)
        
        if df_tokens is not None and not df_tokens.empty:
            # Inline search filtering box
            search_query = st.text_input("🔍 Filter by Ticket No. or Token String").strip().lower()
            if search_query:
                df_tokens = df_tokens[
                    df_tokens['Ticket No.'].astype(str).str.lower().str.contains(search_query) | 
                    df_tokens['Token'].astype(str).str.lower().str.contains(search_query)
                ]
            
            st.caption("📝 **Tip:** Double-click any cell in the **Status** column below to change it directly inside the grid!")

            # Configuration for the interactive data grid
            edited_df = st.data_editor(
                df_tokens,
                use_container_width=True,
                hide_index=True,
                disabled=["Token", "Date Issued", "Ticket No.", "Full Generated Link", "Form URL", "Type"], # Locks other columns
                column_config={
                    "Status": st.column_config.SelectboxColumn(
                        "Status",
                        help="The runtime state of the link",
                        options=["On hold", "Active", "Terminated", "Used"],
                        required=True,
                    )
                },
                key="token_editor"
            )
            
            # Detect changes made inside the data editor grid
            if st.session_state.get("token_editor") and st.session_state.token_editor.get("edited_rows"):
                changes = st.session_state.token_editor["edited_rows"]
                for row_idx, updated_cols in changes.items():
                    if "Status" in updated_cols:
                        # Grab the specific token string from the edited row index
                        token_to_update = df_tokens.iloc[int(row_idx)]["Token"]
                        new_status_value = updated_cols["Status"]
                        
                        # Push updates directly to the Google Sheet backend
                        with st.spinner("Syncing status change to Google Sheets..."):
                            if update_token_status(sheet, token_to_update, new_status_value):
                                st.toast(f"Status updated to {new_status_value}!", icon="🚀")
                                st.cache_data.clear()
                                st.rerun()
        else:
            st.info("The central datastore is currently tracking 0 active links.")
