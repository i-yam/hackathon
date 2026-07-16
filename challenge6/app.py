import streamlit as st
import uuid
import urllib.parse
from datetime import datetime
from config import DATA_FILE, TARGET_SYSTEMS, EMPLOYEE_PHONE_NUMBERS, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER
from data_loader import load_dataset
from extractor import extract_from_text

# Set up the Chrome page configuration
st.set_page_config(page_title="Single Source of Truth (SSOT)", layout="wide", page_icon="🏗️")

# --- Session State Initialization ---
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
    st.session_state.documents = []
    st.session_state.employee_dict = {}
    st.session_state.ifc_objects = []
    st.session_state.ifc_object_types = {}
    st.session_state.extracted_items = []
    st.session_state.activity_feed = []

def log_activity(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.activity_feed.insert(0, f"[{timestamp}] {msg}")

# --- Navigation Sidebar ---
st.sidebar.title("🏗️ Single Source of Truth (SSOT)")
st.sidebar.markdown("*From Informal Communication to Verified Project Information*")

menu = st.sidebar.radio("Navigation Menu", [
    "1. Project Dashboard",
    "2. Input Custom Text",
    "3. AI Extraction Results",
    "4. Verification Queue",
    "5. Categorized Lists"
])

# --- Helper Variables ---
unverified_count = sum(1 for i in st.session_state.extracted_items if i["status"] == "UNVERIFIED")
verified_count = sum(1 for i in st.session_state.extracted_items if i["status"] == "VERIFIED")
linked_ifc_count = sum(1 for i in st.session_state.extracted_items if i.get("ifc_object"))


# ==========================================
# SCREEN 1 — PROJECT DASHBOARD
# ==========================================
if menu == "1. Project Dashboard":
    st.title("📊 Project Dashboard")
    st.markdown("High-level overview of unstructured project communication flowing into project systems.")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Uploaded Documents", len(st.session_state.documents))
    col2.metric("Total Extracted Items", len(st.session_state.extracted_items))
    col3.metric("Unverified Items", unverified_count)
    col4.metric("Verified Items", verified_count)
    col5.metric("Linked IFC Elements", linked_ifc_count)
    
    st.divider()
    
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.subheader("Category Breakdown")
        if not st.session_state.extracted_items:
            st.info("No data extracted yet.")
        else:
            cat_counts = {}
            for item in st.session_state.extracted_items:
                c = item["category"]
                cat_counts[c] = cat_counts.get(c, 0) + 1
            
            # Display as simple tags/cards
            for cat, count in cat_counts.items():
                st.markdown(f"**{cat} Items:** `{count}`")
                
    with col_b:
        st.subheader("Recent Activity Feed")
        if not st.session_state.activity_feed:
            st.caption("No activity yet.")
        else:
            for msg in st.session_state.activity_feed[:8]:
                st.caption(msg)


# ==========================================
# SCREEN 2 — INPUT CUSTOM TEXT
# ==========================================
elif menu == "2. Input Custom Text":
    st.title("✍️ Input Custom Text")
    st.markdown("Paste your own project communication below. The AI will classify the text, extract entities, and add it to the Verification Queue.")
    
    # File Uploader
    uploaded_file = st.file_uploader("Optional: Upload a file to extract text from (.txt, .pdf, .json)", type=["txt", "pdf", "json"])
    
    extracted_file_text = ""
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".txt"):
                extracted_file_text = uploaded_file.read().decode("utf-8")
            elif uploaded_file.name.endswith(".pdf"):
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        extracted_file_text += text + "\n"
            elif uploaded_file.name.endswith(".json"):
                import json
                data = json.load(uploaded_file)
                extracted_file_text = json.dumps(data, indent=2)
        except Exception as e:
            st.error(f"Error reading file: {e}")

    custom_text = st.text_area("Enter your custom text here:", value=extracted_file_text, height=150, placeholder="e.g., The facade delivery is delayed by 3 days. Sarah needs to update the schedule.")
    
    if st.button("Analyze Custom Text", type="primary"):
        if custom_text.strip():
            with st.spinner("AI is classifying and extracting information..."):
                employees_list = list(st.session_state.employee_dict.keys()) if st.session_state.employee_dict else ["Michael Schmidt", "Sarah Weber", "John Miller", "Anna Keller", "David Braun", "Markus Fischer"]
                
                extracted = extract_from_text(
                    custom_text,
                    known_employees=employees_list,
                    known_ifc_objects=st.session_state.ifc_objects
                )
                
                for item in extracted:
                    st.session_state.extracted_items.append({
                        "id": str(uuid.uuid4()),
                        "source_doc": "USER_INPUT",
                        "source_type": "MANUAL",
                        "text": item["extracted_text"],
                        "actionable_detail": item.get("actionable_detail"),
                        "category": item["category"],
                        "owner": item["assigned_person"],
                        "ifc_object": item["related_ifc_object"],
                        "target_system": item["suggested_target_system"] or item["category"],
                        "confidence": item["confidence"],
                        "status": "UNVERIFIED",
                        "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "approval_time": None,
                        "approver": None
                    })
                
                log_activity(f"AI extracted {len(extracted)} items from custom text.")
                st.success(f"✅ Successfully extracted {len(extracted)} items! Please go to '4. Verification Queue' to review and categorize them.")
        else:
            st.warning("Please enter some text to analyze.")
            
    st.divider()
    st.subheader("Optional: Load Project Context")
    st.info("Load the demo dataset or upload your own IFC file to populate the Employee Directory and IFC Objects for entity matching.")
    
    # Custom IFC File Uploader
    ifc_file = st.file_uploader("Upload an IFC file (.ifc) to extract BIM elements dynamically", type=["ifc"])
    
    if ifc_file is not None:
        try:
            content = ifc_file.read().decode("utf-8", errors="ignore")
            import re
            # Lightweight regex to match IFC STEP definitions like: #123= IFCWALL('guid',#42,'W-15',...)
            pattern = re.compile(r'IFC(WALL|DOOR|WINDOW|SPACE)[A-Z]*\s*\([^,]+,[^,]+,\s*\'([^\']+)\'', re.IGNORECASE)
            
            ifc_list = []
            ifc_map = {}
            for match in pattern.finditer(content):
                obj_type = match.group(1).capitalize()
                obj_name = match.group(2)
                
                if obj_name and obj_name not in ifc_map:
                    ifc_list.append(obj_name)
                    ifc_map[obj_name] = obj_type
                    
            if ifc_list:
                st.session_state.ifc_objects = ifc_list
                st.session_state.ifc_object_types = ifc_map
                st.success(f"✅ Extracted {len(ifc_list)} IFC objects directly from your uploaded file!")
            else:
                st.warning("Could not find any named Walls, Doors, Windows, or Spaces in the uploaded IFC file.")
        except Exception as e:
            st.error(f"Error reading IFC file: {e}")

    if not st.session_state.data_loaded:
        if st.button("Load Hackathon Context (Demo Data)"):
            dataset = load_dataset(DATA_FILE)
            if dataset:
                st.session_state.documents = dataset.get("documents", [])
                # Create a reverse dictionary mapping Name -> Role
                emp_dir = dataset.get("employee_directory", {})
                st.session_state.employee_dict = {name: role.upper() for role, name in emp_dir.items()}
                
                # Create a flat list for the extractor and a map for the UI
                ifc_map = {}
                ifc_list = []
                for obj_type, obj_list in dataset.get("ifc_objects", {}).items():
                    # "walls" -> "Wall"
                    clean_obj_type = obj_type.capitalize().rstrip('s')
                    ifc_list.extend(obj_list)
                    for obj_id in obj_list:
                        ifc_map[obj_id] = clean_obj_type
                st.session_state.ifc_objects = ifc_list
                st.session_state.ifc_object_types = ifc_map
                
                st.session_state.data_loaded = True
                log_activity("Loaded Employee Directory and IFC Context.")
                st.rerun()
            else:
                st.error("Failed to load dataset.")
    else:
        st.success("✅ Employee Directory and IFC Objects loaded!")


# ==========================================
# SCREEN 3 — AI EXTRACTION RESULTS
# ==========================================
elif menu == "3. AI Extraction Results":
    st.title("🤖 AI Extraction Results")
    st.markdown("The AI has extracted the following project-relevant information. It is currently marked as **UNVERIFIED**.")
    
    if not st.session_state.extracted_items:
        st.warning("No data extracted. Please go to Data Ingestion and Analyze.")
    else:
        for item in st.session_state.extracted_items:
            with st.container(border=True):
                st.markdown(f"### {item['category']} (Confidence: {item['confidence']*100:.0f}%)")
                if item.get('actionable_detail'):
                    st.markdown(f"**🎯 Key Detail Extracted:** `{item['actionable_detail'].capitalize()}`")
                st.markdown(f"**Source:** `{item['source_doc']}` | **Status:** 🟠 {item['status']}")
                st.markdown(f"> *\"{item['text']}\"*")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if item["owner"]:
                        role = st.session_state.employee_dict.get(item["owner"], "UNKNOWN ROLE")
                        st.success(f"👤 **Owner Found:** {item['owner']} ({role})")
                    else:
                        st.info("👤 Owner: None detected")
                        
                with col_b:
                    if item["ifc_object"]:
                        obj_id = item["ifc_object"]
                        obj_type = st.session_state.ifc_object_types.get(obj_id, "Unknown Type")
                        st.success(f"✓ **IFC Match Found:** `{obj_id}` (Type: {obj_type})")
                    else:
                        st.info("No IFC links detected.")


# ==========================================
# SCREEN 4 — VERIFICATION QUEUE
# ==========================================
elif menu == "4. Verification Queue":
    st.title("✅ Human Verification Queue")
    st.markdown("Human-in-the-loop review. Only verified items can be transferred to destination systems.")
    
    unverified_items = [i for i in st.session_state.extracted_items if i["status"] == "UNVERIFIED"]
    
    if not unverified_items:
        st.success("Queue is empty! All items have been processed.")
    else:
        # Bulk Actions
        if st.button("Bulk Approve All"):
            for item in st.session_state.extracted_items:
                if item["status"] == "UNVERIFIED":
                    item["status"] = "VERIFIED"
                    item["approval_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    item["approver"] = "Demo User"
            log_activity(f"Bulk approved {len(unverified_items)} items.")
            st.rerun()
            
        st.divider()
        
        for item in unverified_items:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    if item.get('actionable_detail'):
                        st.success(f"**Extracted Detail:** {item['actionable_detail'].capitalize()}")
                    st.markdown(f"> *\"{item['text']}\"*")
                    
                    available_categories = list(TARGET_SYSTEMS.keys())
                    default_index = available_categories.index(item['category']) if item['category'] in available_categories else 0
                    
                    new_cat = st.selectbox(
                        "Verify & Assign Category:",
                        available_categories,
                        index=default_index,
                        key=f"cat_{item['id']}"
                    )
                    
                    team_members = list(st.session_state.employee_dict.keys()) if st.session_state.employee_dict else ["Michael Schmidt", "Sarah Weber", "John Miller", "Anna Keller", "David Braun", "Markus Fischer"]
                    if "Unassigned" not in team_members:
                        team_members.append("Unassigned")
                        
                    current_owner = item['owner'] if item['owner'] in team_members else "Unassigned"
                    owner_index = team_members.index(current_owner)
                    
                    new_owner = st.selectbox(
                        "Assign To:",
                        team_members,
                        index=owner_index,
                        key=f"owner_{item['id']}"
                    )
                with col2:
                    st.write("") # Spacing
                    st.write("") # Spacing
                    # Action buttons
                    if st.button("Verify & Assign", key=f"app_{item['id']}", type="primary"):
                        for ref in st.session_state.extracted_items:
                            if ref["id"] == item["id"]:
                                ref["category"] = new_cat
                                ref["owner"] = new_owner if new_owner != "Unassigned" else None
                                ref["target_system"] = TARGET_SYSTEMS.get(new_cat, new_cat)
                                ref["status"] = "VERIFIED"
                                ref["approval_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                ref["approver"] = "Human User"
                        log_activity(f"Verified and assigned item to {new_cat}.")
                        st.rerun()
                    
                    if st.button("Reject", key=f"rej_{item['id']}"):
                        for ref in st.session_state.extracted_items:
                            if ref["id"] == item["id"]:
                                ref["status"] = "REJECTED"
                        log_activity(f"Rejected {item['category']} item.")
                        st.rerun()


# ==========================================
# SCREEN 5 — CATEGORIZED LISTS
# ==========================================
elif menu == "5. Categorized Lists":
    st.title("📋 Categorized Lists")
    st.markdown("All verified information automatically organized into their respective category lists.")
    
    verified_items = [i for i in st.session_state.extracted_items if i["status"] == "VERIFIED"]
    
    if not verified_items:
        st.info("No verified items yet. Go to the Verification Queue to approve some.")
    else:
        grouping_mode = st.radio("Group items by:", ["Category", "Assigned Person"], horizontal=True)
        st.divider()
        
        # Group items
        grouped = {}
        for item in verified_items:
            if grouping_mode == "Category":
                key = item["category"] or "Uncategorized"
            else:
                key = item["owner"] or "Unassigned"
                
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(item)
            
        group_names = list(grouped.keys())
        tabs = st.tabs(group_names)
        
        for tab, g_name in zip(tabs, group_names):
            with tab:
                st.subheader(f"{g_name} List")
                for item in grouped[g_name]:
                    with st.container(border=True):
                        st.markdown(f"**Item:** {item['text']}")
                        owner_text = item['owner'] if item['owner'] else 'Unassigned'
                        st.markdown(f"**Assigned To:** {owner_text} | **Target System:** {item['target_system']}")
                        
                        with st.expander("Details & Audit Trail"):
                            st.caption(f"**Confidence:** {item['confidence']*100:.0f}%")
                            if item['ifc_object']:
                                obj_id = item["ifc_object"]
                                obj_type = st.session_state.ifc_object_types.get(obj_id, "Unknown Type")
                                st.caption(f"**Linked IFC:** {obj_id} (Type: {obj_type})")
                            st.caption(f"**Extraction Timestamp:** {item['extraction_time']}")
                            st.caption(f"**Verification Timestamp:** {item['approval_time']}")
                            
                            # WhatsApp Integration
                            if item['owner'] and item['owner'] in EMPLOYEE_PHONE_NUMBERS:
                                if st.button(f"📱 Auto-Send WhatsApp to {item['owner']}", key=f"wa_{item['id']}"):
                                    with st.spinner("Sending message via Twilio..."):
                                        try:
                                            from twilio.rest import Client
                                            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                                            
                                            target_number = EMPLOYEE_PHONE_NUMBERS[item['owner']]
                                            message_body = f"Hi {item['owner']},\n\nYou have a new {item['category']} item assigned to you for the Green Tower project:\n\n\"{item['text']}\"\n\nPlease review this in the {item['target_system']}."
                                            
                                            message = client.messages.create(
                                                from_=TWILIO_WHATSAPP_NUMBER,
                                                body=message_body,
                                                to=f"whatsapp:{target_number}"
                                            )
                                            st.success(f"✅ Message sent to Twilio! (Tracking SID: {message.sid})")
                                        except Exception as e:
                                            st.error(f"Failed to send message: {e}")