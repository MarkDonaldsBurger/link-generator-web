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
        
        # Handle column name variations
        if "Ticket No." not in df.columns:
            if "Ticket Number" in df.columns:
                df = df.rename(columns={"Ticket Number": "Ticket No."})
            elif "Ticket_No" in df.columns:
                df = df.rename(columns={"Ticket_No": "Ticket No."})
        
        # Build the full clickable/copyable URL
        base_app_url = "https://dynamiclinkgeneratorpy-jvrqcasnbsduy6hwwmco58.streamlit.app/"
        if "Token" in df.columns:
            df["Full Generated Link"] = base_app_url + "?token=" + df["Token"].astype(str)
        
        # KEY CHANGE: Ensure "Status" is the last item in this list 
        # so it renders at the far right of the table
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
        # --------------------------------------------------
        # GATEKEEPER VIEW
        # --------------------------------------------------
        st.title("🛡️ Internal Verification Gateway")
        st.write("This workflow workspace is restricted strictly to authorized department personnel.")
        
        user_email = st.text_input("Enter your official office email address:", placeholder="username@dti.gov.ph").strip().lower()

        if user_email:
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
                        
                        if status != "Active":
                            st.error(f"Access Denied: This link assignment is no longer accessible. Current Status: **{status}**.")
                        else:
                            st.success("Verification successful! Access granted.")
                            st.markdown("### Click below to proceed to your assignment workspace:")
                            
                            st.markdown(
                                f"""
                                <div style="text-align: center; margin-top: 20px;">
                                    <a href="{form_url}" target="_blank" rel="noopener noreferrer" style="
                                        display: block;
                                        width: 100%;
                                        background-color: #ff4b4b;
                                        color: white;
                                        text-decoration: none;
                                        padding: 0.75rem 1rem;
                                        border-radius: 0.5rem;
                                        font-size: 1rem;
                                        font-weight: bold;
                                        box-sizing: border-box;
                                        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
                                    ">
                                        👉 Open Microsoft Form Workspace (Opens in Clean Tab)
                                    </a>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
    else:
        # --------------------------------------------------
        # CONSOLE VIEW
        # --------------------------------------------------
        st.title("🔗 Dynamic Link Generator & Management Console")
        
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
                # Top Filters
                filter_col1, filter_col2 = st.columns([2, 1])
                
                with filter_col1:
                    search_query = st.text_input("🔍 Filter by Ticket No. or Token String").strip().lower()
                
                with filter_col2:
                    type_filter = st.selectbox("📂 Filter by Link Type", ["All", "INTERNAL", "EXTERNAL"])

                # Apply Filters
                if search_query:
                    df_tokens = df_tokens[
                        df_tokens['Ticket No.'].astype(str).str.lower().str.contains(search_query) | 
                        df_tokens['Token'].astype(str).str.lower().str.contains(search_query)
                    ]
                
                if type_filter != "All":
                    df_tokens = df_tokens[df_tokens['Type'] == type_filter]
                
                # Display Read-Only Dataframe
                st.dataframe(df_tokens, use_container_width=True, hide_index=True)

                # ==========================================
                # NEW FEATURE: QUICK STATUS UPDATE TOOL
                # ==========================================
                st.divider()
                st.markdown("#### ✏️ Quick Status Update")
                
                # Create a unique readable ID for the dropdown
                df_tokens["Update_ID"] = df_tokens["Ticket No."].astype(str) + " [" + df_tokens["Type"] + "]"
                
                update_col1, update_col2, update_col3 = st.columns([2, 2, 1.5])
                
                with update_col1:
                    selected_id = st.selectbox("1. Select Record to Update", options=["-- Select --"] + df_tokens["Update_ID"].tolist())
                
                if selected_id != "-- Select --":
                    # Get the data for the selected record
                    target_row = df_tokens[df_tokens["Update_ID"] == selected_id].iloc[0]
                    current_status = target_row["Status"]
                    target_token = target_row["Token"]
                    
                    with update_col2:
                        status_options = ["On hold", "Active", "Terminated", "Used"]
                        # Set the dropdown to whatever the current status is
                        current_idx = status_options.index(current_status) if current_status in status_options else 0
                        new_status = st.selectbox("2. Select New Status", options=status_options, index=current_idx)
                    
                    with update_col3:
                        st.write("") # Blank spaces to align the button with the dropdown fields
                        st.write("")
                        
                        # Only show the update button if they actually changed the dropdown
                        if new_status != current_status:
                            if st.button("💾 Confirm Update", type="primary", use_container_width=True):
                                with st.spinner("Syncing to Google Sheets..."):
                                    if update_token_status(sheet, target_token, new_status):
                                        st.toast(f"Status successfully changed to {new_status}!", icon="✅")
                                        st.cache_data.clear()
                                        st.rerun()
            else:
                st.info("The central datastore is currently tracking 0 active links.")
