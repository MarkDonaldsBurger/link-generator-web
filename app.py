import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# ======================================================
# Page Configuration
# ======================================================

st.set_page_config(
    page_title="Secure Access Portal",
    page_icon="🔐",
    layout="wide"
)

# ======================================================
# Custom CSS
# ======================================================

st.markdown("""
<style>

.block-container {
    padding-top: 1rem;
    padding-bottom: 0rem;
    padding-left: 2rem;
    padding-right: 2rem;
}

#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}
.stAppDeployButton {display:none;}
[data-testid="stToolbar"] {display:none;}

iframe{
    border:none;
}

.green-btn{
    display:block;
    width:100%;
    padding:14px;
    text-align:center;
    background:#28a745;
    color:white !important;
    border-radius:8px;
    font-size:18px;
    font-weight:bold;
    text-decoration:none;
    transition:0.2s;
}

.green-btn:hover{
    background:#218838;
}

</style>
""", unsafe_allow_html=True)

# ======================================================
# Connection
# ======================================================

def get_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception:
        return None

conn = get_connection()

if conn is None:
    st.error("The secure gateway is taking longer than usual to respond. Please refresh.")
    st.stop()

# ======================================================
# Read Token
# ======================================================

user_token = st.query_params.get("token")

if not user_token:
    st.error("### Access Required")
    st.write("No security token detected.")
    st.stop()

# ======================================================
# Read Sheet
# ======================================================

df = conn.read(ttl=0)

token_data = df[df["Token"].astype(str) == str(user_token)]

if token_data.empty:
    st.error("### Invalid Link")
    st.write("The link is not recognized by our system.")
    st.stop()

# ======================================================
# Read Values
# ======================================================

current_status = token_data["Status"].values[0]

try:
    form_type = str(token_data.iloc[0, 5]).strip().upper()
except Exception:
    form_type = "EXTERNAL"

EXTERNAL_FORM = "https://forms.office.com/r/KchEak7FWA?embed=true"

# IMPORTANT:
# No ?embed=true
INTERNAL_FORM = "https://forms.office.com/r/5s3GA7Df0T"

# ======================================================
# Logic
# ======================================================

if current_status == "Active":

    # Mark as Used
    df.loc[df["Token"].astype(str) == str(user_token), "Status"] = "Used"
    conn.update(data=df)

    if form_type == "INTERNAL":
        st.info("""
Your identity has been successfully verified.
""")
        
        # This is the standard, browser-friendly way to navigate away
        st.link_button("👉 Continue to Microsoft Form", url=INTERNAL_FORM, type="primary")

        st.caption("⚠️ This is a one-time access link.")

    else:

        st.toast("Loading External Registration Form...")

        st.components.v1.iframe(
            EXTERNAL_FORM,
            height=2000,
            scrolling=False
        )

        st.caption("⚠️ This is a one-time access link.")

elif current_status in ["Used", "Terminated"]:

    st.warning("### Link Expired")
    st.write("This secure registration link has already been used or has expired.")

elif current_status == "On hold":

    st.info("### Access Pending")
    st.write("This registration link is currently On Hold.")

else:

    st.error("### Access Restricted")
    st.write("There is a status issue with this token. Please contact support.")
