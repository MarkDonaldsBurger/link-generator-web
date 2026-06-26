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

# Dialog prompt that opens cleanly when links are successfully made
@st.dialog("🚀 Link Successfully Generated!")
def show_success_popup(url, link_type, ticket):
    st.success(f"Successfully created a new **{link_type}** tracking link.")
    st.write(f"**Ticket Ref:** {ticket}")
    
    # Text area holding the link + automated copy helper
    st.text_area("Copy Dynamic Link:", value=url, height=80, help="Click anywhere inside or click the copy shortcut tool.")
    
    if st.button("Close & Refresh Dashboard", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 3. Runtime Routing & Web Interface Construction
sheet = get_sheet()

if sheet:
    # Check if the visitor arrived via an generated dynamic link token link
    query_params = st.query_params
    token_param = query_params.get("token")

    if token_param:
        # --------------------------------------------------
        # GATEKEEPER VIEW: Triggered via ?token= URL parameter
        # --------------------------------------------------
        st.title("🛡️ Internal Verification Gateway")
        st.write("This workflow workspace is restricted strictly to authorized department personnel.")
        
        # Request their official organizational context credentials
        user_email = st.text_input("Enter your official office email address:", placeholder="username@dti.gov.ph").strip().lower()

        if user_email:
            # Enforce explicit email suffix boundary check
            if not user_email.endswith("@dti.gov.ph"):
                st.error("Access Denied: You must use an authorized organizational email address (@dti.gov.ph) to access this form.")
            else:
                with st.spinner("Verifying runtime link state credentials..."):
                    df_tokens = load_tokens_from_sheet(sheet)
                    matched_row = df_tokens[df_tokens["Token"] == token_param] if df_tokens is not None else pd.DataFrame()
                    
                    if matched_row.empty:
                        st.error("Invalid Link Sequence: The system cannot locate this transactional token tracking key.")
                    else:
                        status = matched_row.iloc[0]["Status"]
                        form_url = matched_row.iloc[0]["Form URL"]
                        
                        # Verify the token lifetime status is active
                        if status != "Active":
                            st.error(f"Access Denied: This link assignment is no longer accessible. Current Status: **{status}**.")
                        else:
                            st.success("Verification successful! Access granted.")
                            st.markdown("### Click below to proceed to your assignment workspace:")
                            
                            # MODIFIED LINE (Old line 132): Broken out of the iframe using target="_blank" HTML wrapper 
                            st.markdown(
                                f"""
                                <a href="{form_url}" target="_blank" style="text-decoration: none;">
                                    <button style="
                                        width: 100%;
                                        background-color: #ff4b4b;
                                        color: white;
                                        border: none;
                                        padding: 0.5rem 1rem;
                                        border-radius: 0.5rem;
                                        cursor: pointer;
                                        font-size: 1rem;
                                        font-weight: 500;
                                        line-height: 1.6;
                                        text-align: center;
                                    ">
                                        👉 Open Microsoft Form Workspace (Opens New Tab)
                                    </button>
                                </a>
                                """,
                                unsafe_allow_html=True
                            )
    else:
        # --------------------------------------------------
        # CONSOLE VIEW: Standard administrative control room
        # --------------------------------------------------
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
                        current_df = load_tokens_from_sheet(sheet)
                        duplicate_exists = False
                        if current_df is not None and not current_df.empty:
                            duplicate_exists = not current_df[
                                (current_df["Ticket No."].astype(str) == str(ticket_no.strip())) & 
                                (current_df["Type"] == "EXTERNAL")
                            ].empty
                        
                        if duplicate_exists:
                            st.error(f"Validation Error: Ticket No. '{ticket_no.strip()}' already has an active EXTERNAL link.")
                        else:
                            with st.spinner("Generating External Link..."):
                                token, url = generate_client_link(sheet, ticket_no.strip(), initial_status, "EXTERNAL")
                                if token:
                                    show_success_popup(url, "EXTERNAL", ticket_no.strip())
                    else:
                        st.warning("Please fill in the Ticket Number field.")
                        
            with btn_int:
                if st.button("Generate Internal Link", use_container_width=True):
                    if ticket_no.strip():
                        current_df = load_tokens_from_sheet(sheet)
                        duplicate_exists = False
                        if current_df is not None and not current_df.empty:
                            duplicate_exists = not current_df[
                                (current_df["Ticket No."].astype(str) == str(ticket_no.strip())) & 
                                (current_df["Type"] == "INTERNAL")
                            ].empty
                        
                        if duplicate_exists:
                            st.error(f"Validation Error: Ticket No. '{ticket_no.strip()}' already has an active INTERNAL link.")
                        else:
                            with st.spinner("Generating Internal Link..."):
                                token, url = generate_client_link(sheet, ticket_no.strip(), initial_status, "INTERNAL")
                                if token:
                                    show_success_popup(url, "INTERNAL", ticket_no.strip())
                    else:
                        st.warning("Please fill in the Ticket Number field.")

        with col2:
            st.subheader("Real-Time Token Sync View")
            
            if st.button("🔄 Refresh Shared Sheet Data"):
                st.cache_data.clear()
                st.rerun()
                
            df_tokens = load_tokens_from_sheet(sheet)
            
            if df_tokens is not None and not df_tokens.empty:
                search_query = st.text_input("🔍 Filter by Ticket No. or Token String").strip().lower()
                if search_query:
                    df_tokens = df_tokens[
                        df_tokens['Ticket No.'].astype(str).str.lower().str.contains(search_query) | 
                        df_tokens['Token'].astype(str).str.lower().str.contains(search_query)
                    ]
                
                st.caption("📝 **Tip:** Double-click any cell in the **Status** column below to change it directly inside the grid!")

                edited_df = st.data_editor(
                    df_tokens,
                    use_container_width=True,
                    hide_index=True,
                    disabled=["Token", "Date Issued", "Ticket No.", "Full Generated Link", "Form URL", "Type"], 
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
                
                if st.session_state.get("token_editor") and st.session_state.token_editor.get("edited_rows"):
                    changes = st.session_state.token_editor["edited_rows"]
                    for row_idx, updated_cols in changes.items():
                        if "Status" in updated_cols:
                            token_to_update = df_tokens.iloc[int(row_idx)]["Token"]
                            new_status_value = updated_cols["Status"]
                            
                            with st.spinner("Syncing status change to Google Sheets..."):
                                if update_token_status(sheet, token_to_update, new_status_value):
                                    st.toast(f"Status updated to {new_status_value}!", icon="🚀")
                                    st.cache_data.clear()
                                    st.rerun()
            else:
                st.info("The central datastore is currently tracking 0 active links.")
