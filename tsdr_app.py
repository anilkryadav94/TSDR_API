import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO


st.set_page_config(layout="wide")


# Load usernames and passwords from Streamlit secrets
AUTH_USERS = st.secrets["credentials"]

# Session state to track login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Login UI
if not st.session_state.logged_in:
    st.title("🔒 Login Required")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in AUTH_USERS and AUTH_USERS[username] == password:
            st.session_state.logged_in = True
            st.success("✅ Login successful!")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")

else:
    st.success(f"✅ Welcome! Let start fetching publically available TM records from TSDR.")
    # 👉 Continue with rest of your app

    st.title("USPTO Trademark Data")

    # 🔑 API Key Input
    api_key = st.secrets["API_KEY"]

    # 📥 Serial Numbers Input
    app_numbers_input = st.text_area("Enter Serial Numbers (comma-separated):", "97439760,77434372")

    start_btn = st.button("Fetch Data")


    # Function to fetch and parse TSDR XML
    def fetch_tsdr_data(app_number, api_key):
        url = f"https://tsdrapi.uspto.gov/ts/cd/casestatus/sn{app_number}/info.xml"
        headers = {"USPTO-API-KEY": api_key}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return {"Application Number": app_number, "Error": f"HTTP {response.status_code}"}

            root = ET.fromstring(response.content)

            ns = {
                "ns": "http://www.wipo.int/standards/XMLSchema/ST96/Trademark",
                "ns1": "http://www.wipo.int/standards/XMLSchema/ST96/Common"
            }

            data = {
                "Application Number": app_number,
                "Application Date": "N/A",
                "Status": "N/A",
                "Publication Date": "N/A",
                "First Use Date(s)": "N/A",
                "Use in Commerce Date(s)": "N/A",
                "NOA Date": "N/A",
                "Registration Number": "N/A",
                "Registration Date": "N/A",
                "Register Type": "N/A",
                "Mark Name": "N/A",
                "Mark Type (Category)": "N/A",
                "International Classes": "N/A",
                "Current Owner Name": "N/A",
                "Filed as ITU": "No"
            }

            # Application Date
            app_date = root.find(".//ns:ApplicationDate", ns)
            if app_date is not None:
                data["Application Date"] = app_date.text[:10]

            # Status
            status = root.find(".//ns:MarkCurrentStatusExternalDescriptionText", ns)
            if status is not None:
                data["Status"] = status.text

            # Publication Date
            pub_date = root.find(".//ns:PublicationBag/ns:Publication/ns1:PublicationDate", ns)
            if pub_date is not None and pub_date.text:
                data["Publication Date"] = pub_date.text[:10]

            # First Use
            first_use = root.findall(".//ns:FirstUsedDate", ns)
            if first_use:
                data["First Use Date(s)"] = ", ".join([el.text[:10] for el in first_use if el.text])

            # Use in Commerce
            use_commerce = root.findall(".//ns:FirstUsedCommerceDate", ns)
            if use_commerce:
                data["Use in Commerce Date(s)"] = ", ".join([el.text[:10] for el in use_commerce if el.text])

            # NOA Date
            noa_date = root.find(".//ns:AllowanceNoticeDate", ns)
            if noa_date is not None and noa_date.text:
                data["NOA Date"] = noa_date.text[:10]

            # Registration Number
            reg_num = root.find(".//ns1:RegistrationNumber", ns)
            if reg_num is not None:
                data["Registration Number"] = reg_num.text

            # Registration Date
            reg_date = root.find(".//ns1:RegistrationDate", ns)
            if reg_date is not None:
                data["Registration Date"] = reg_date.text[:10]

            # Register Type
            reg_type_nodes = root.findall(".//ns:MarkEventDescriptionText", ns)
            for node in reg_type_nodes:
                if node.text:
                    text = node.text.upper()
                    if "PRINCIPAL" in text:
                        data["Register Type"] = "Principal"
                        break
                    elif "SUPPLEMENTAL" in text:
                        data["Register Type"] = "Supplemental"
                        break

            # Mark Name
            mark_name = root.find(".//ns:MarkVerbalElementText", ns)
            if mark_name is None:
                mark_name = root.find(".//ns:MarkSignificantVerbalElementText", ns)
            if mark_name is not None:
                data["Mark Name"] = mark_name.text

            # Mark Type (Category)
            mark_type = root.find(".//ns:MarkCategory", ns)
            if mark_type is not None:
                data["Mark Type (Category)"] = mark_type.text

            # International Classes and Descriptions
            class_info_list = []
            all_elements = list(root.iter())
            for idx, elem in enumerate(all_elements):
                if elem.tag == "{http://www.wipo.int/standards/XMLSchema/ST96/Trademark}GoodsServicesDescriptionText":
                    for back in range(idx - 1, max(idx - 5, -1), -1):
                        if all_elements[back].tag == "{http://www.wipo.int/standards/XMLSchema/ST96/Trademark}ClassNumber":
                            class_num = all_elements[back].text.strip()
                            desc = elem.text.strip()
                            class_info_list.append(f"{class_num} - {desc}")
                            break
            if class_info_list:
                data["International Classes"] = "\n\n".join(class_info_list)

            # Current Owner Name
            all_nodes = list(root.iter())
            for i, node in enumerate(all_nodes):
                if node.tag.endswith("CommentText") and node.text and "OWNER AT PUBLICATION" in node.text.upper():
                    for j in range(i + 1, min(i + 6, len(all_nodes))):
                        next_node = all_nodes[j]
                        if next_node.tag.endswith("OrganizationStandardName") and next_node.text:
                            data["Current Owner Name"] = next_node.text.strip()
                            break
                    break

            # Filed as ITU
            filed_itu = "No"
            for event_code in root.findall(".//ns:MarkEventCode", ns):
                if event_code is not None and event_code.text == "AITUA":
                    filed_itu = "Yes"
                    break
            data["Filed as ITU"] = filed_itu

            return data

        except Exception as e:
            return {
                "Application Number": app_number,
                "Error": str(e)
            }


    # 🚀 Process only when button is clicked and API key is provided
    if start_btn and api_key:
        app_numbers = [num.strip() for num in app_numbers_input.split(",") if num.strip()]
        all_data = []

        with st.spinner("Fetching data..."):
            for sn in app_numbers:
                data = fetch_tsdr_data(sn, api_key)
                all_data.append(data)

        df = pd.DataFrame(all_data)
        st.success("✅ Data fetched successfully!")
        st.dataframe(df)

        # 📤 Excel Download
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        st.download_button(
            label="📥 Download Excel",
            data=buffer.getvalue(),
            file_name="tsdr_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    elif start_btn and not api_key:
        st.error("⚠️ Please enter your USPTO API Key.")
