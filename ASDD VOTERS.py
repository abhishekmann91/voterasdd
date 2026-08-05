import streamlit as st
import pandas as pd
import io
import re
import os
import pypdf
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

# Cache configuration files
CACHE_FILE = "master_voter_pdf_cache.pkl"
METADATA_FILE = "master_voter_pdf_metadata.txt"

# Dynamic Mapping Configuration for the 5 requested categories
PDF_CATEGORIES = {
    "Permanently Shifted": {
        "annexure": "Annexure-II",
        "title": "List of ASDD Electors: Category - Permanently Shifted",
        "last_col": "Category / Remarks",
        "default_remark": "Permanently Shifted",
        "filename_suffix": "Permanently_Shifted"
    },
    "Death": {
        "annexure": "Annexure-III",
        "title": "List of ASDD Electors: Category - Dead / Death Cases",
        "last_col": "Category / Remarks",
        "default_remark": "Dead",
        "filename_suffix": "Dead_Cases"
    },
    "Already Enrolled": {
        "annexure": "Annexure-IV",
        "title": "List of ASDD Electors: Category - Duplicate / Already Enrolled",
        "last_col": "Category / Remarks",
        "default_remark": "Already Enrolled / Duplicate",
        "filename_suffix": "Duplicate_Already_Enrolled"
    },
    "Absent": {
        "annexure": "Annexure-V",
        "title": "List of ASDD Electors: Category - Absent",
        "last_col": "Remarks (Refused to sign etc.)",
        "default_remark": "Absent",
        "filename_suffix": "Absent"
    },
    "Others": {
        "annexure": "Annexure-V",
        "title": "List of ASDD Electors: Category - Others",
        "last_col": "Remarks (Refused to sign etc.)",
        "default_remark": "Others",
        "filename_suffix": "Others"
    }
}

# Initialize session state variables
if 'voter_df' not in st.session_state:
    st.session_state['voter_df'] = None
if 'ac_info' not in st.session_state:
    st.session_state['ac_info'] = ""
if 'part_info' not in st.session_state:
    st.session_state['part_info'] = ""
if 'pdf_filename' not in st.session_state:
    st.session_state['pdf_filename'] = ""

def classify_reason(reason):
    """Maps the parsed 'Uncollectable Reason' to one of the five specific groups."""
    r_lower = str(reason).lower().strip()
    if "shifted" in r_lower:
        return "Permanently Shifted"
    elif "death" in r_lower or "dead" in r_lower:
        return "Death"
    elif "already enrolled" in r_lower or "alreadyenrolled" in r_lower or "duplicate" in r_lower:
        return "Already Enrolled"
    elif "absent" in r_lower:
        return "Absent"
    else:
        return "Others"

def parse_eci_pdf(file_bytes):
    """
    Parses vector text ECI PDF documents page by page to extract voter tables 
    and document headers dynamically.
    """
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    extracted_rows = []
    
    ac_name = "Not Found"
    part_no = "Not Found"
    
    # Regex pattern to match document header structures
    # Example: "AC: 6-RITHALA; Part: 243-SECTOR-1, ROHINI"
    ac_part_pattern = re.compile(r'AC:\s*(.*?);\s*Part:\s*([^\n\r]+)')
    
    # Regex pattern to match tabular row data cleanly.
    # Ex: "1 25 URO2221496 BABU LAL UTTAM CHAND (Father) (38) Permanently Shifted"
    row_pattern = re.compile(
        r'^\s*(\d+)\s+(\d+)\s+([A-Z0-9]{10})\s+(.+?)\s+([^\(]+?\s*\([A-Za-z\s\/]+\))\s*\((\d+)\)\s*(.*)$'
    )
    
    for page in reader.pages:
        text = page.extract_text()
        if not text:
            continue
            
        lines = text.split('\n')
        for line in lines:
            line_str = line.strip()
            
            # 1. Attempt header info parsing
            if "AC:" in line_str and "Part:" in line_str:
                match_ac = ac_part_pattern.search(line_str)
                if match_ac:
                    ac_name = match_ac.group(1).strip()
                    part_no = match_ac.group(2).strip()
            
            # 2. Attempt row data matching
            match_row = row_pattern.match(line_str)
            if match_row:
                s_no = match_row.group(1)
                serial_no = match_row.group(2)  # SL No. in the part
                epic_no = match_row.group(3)    # EPIC Number
                elector_name = match_row.group(4)
                relative_details = match_row.group(5)
                age = match_row.group(6)
                uncollectable_reason = match_row.group(7).strip()
                
                category = classify_reason(uncollectable_reason)
                
                extracted_rows.append({
                    'serial_no': serial_no,
                    'epic_no': epic_no,
                    'elector_name': elector_name,
                    'relative_name': relative_details,
                    'age': age,
                    'uncollectable_reason': uncollectable_reason,
                    'category': category
                })
                
    df = pd.DataFrame(extracted_rows)
    return df, ac_name, part_no

def load_cached_data():
    """Tries to read persisted dataset and parameters from disk."""
    if os.path.exists(CACHE_FILE) and os.path.exists(METADATA_FILE):
        try:
            df = pd.read_pickle(CACHE_FILE)
            with open(METADATA_FILE, "r") as f:
                lines = f.read().splitlines()
            ac_info = lines[0] if len(lines) > 0 else ""
            part_info = lines[1] if len(lines) > 1 else ""
            filename = lines[2] if len(lines) > 2 else ""
            return df, ac_info, part_info, filename
        except Exception:
            return None, "", "", ""
    return None, "", "", ""

def save_to_cache(df, ac_info, part_info, filename):
    """Saves the parsed data and metadata to disk."""
    try:
        df.to_pickle(CACHE_FILE)
        with open(METADATA_FILE, "w") as f:
            f.write(f"{ac_info}\n{part_info}\n{filename}")
    except Exception as e:
        st.error(f"Unable to write cache files: {e}")

def clear_cache():
    """Deletes cached local files and resets the current session state."""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    if os.path.exists(METADATA_FILE):
        os.remove(METADATA_FILE)
    st.session_state['voter_df'] = None
    st.session_state['ac_info'] = ""
    st.session_state['part_info'] = ""
    st.session_state['pdf_filename'] = ""
    st.rerun()

def generate_pdf_report(data_rows, ac_name, part_no, category_config):
    """Generates official ReportLab PDF matched strictly to the chosen Annexure template."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    style_annexure = ParagraphStyle(
        'DocAnnexure',
        parent=styles['Heading2'],
        alignment=TA_CENTER,
        fontSize=12,
        leading=14,
        fontName='Helvetica-Bold',
        spaceAfter=4
    )
    style_header = ParagraphStyle(
        'DocHeader',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=10,
        leading=12,
        fontName='Helvetica-Bold',
        spaceAfter=4
    )
    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=11,
        leading=13,
        fontName='Helvetica-Bold',
        spaceAfter=15
    )
    style_cell = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=10.5
    )
    style_cell_bold = ParagraphStyle(
        'CellHeader',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=10.5,
        fontName='Helvetica-Bold'
    )

    story.append(Paragraph(category_config['annexure'], style_annexure))
    story.append(Paragraph(f"AC No. & Name: {ac_name} | Part No.: {part_no}", style_header))
    story.append(Paragraph(category_config['title'], style_title))

    table_headers = [
        Paragraph("<b>S. No.</b>", style_cell_bold),
        Paragraph("<b>EPIC No.</b>", style_cell_bold),
        Paragraph("<b>SL No. in the Part</b>", style_cell_bold),
        Paragraph("<b>Name of the Elector</b>", style_cell_bold),
        Paragraph("<b>Name of Relative</b>", style_cell_bold),
        Paragraph(f"<b>{category_config['last_col']}</b>", style_cell_bold)
    ]
    
    table_data = [table_headers]
    for idx, row in enumerate(data_rows, start=1):
        table_data.append([
            Paragraph(str(idx), style_cell),
            Paragraph(str(row.get('epic_no', '')), style_cell),
            Paragraph(str(row.get('serial_no', '')), style_cell),
            Paragraph(str(row.get('elector_name', '')), style_cell),
            Paragraph(str(row.get('relative_name', '')), style_cell),
            Paragraph(str(row.get('remarks', '')), style_cell)
        ])

    col_widths = [30, 80, 60, 115, 115, 123]
    voter_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    voter_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(voter_table)
    story.append(Spacer(1, 25))

    footer_table_data = [
        [
            Paragraph("<b>Sign of BLO:</b> _____________________", style_cell),
            Paragraph("<b>Sign of BLA-2:</b>", style_cell)
        ],
        ["", Paragraph("(i) __________________________", style_cell)],
        ["", Paragraph("(ii) __________________________", style_cell)],
        ["", Paragraph("(iii) __________________________", style_cell)],
        ["", Paragraph("(iv) __________________________", style_cell)]
    ]
    
    footer_table = Table(footer_table_data, colWidths=[240, 283])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    
    story.append(KeepTogether([footer_table]))

    doc.build(story)
    buffer.seek(0)
    return buffer

# --- Streamlit Execution Flow ---
st.set_page_config(page_title="ECI PDF ASDD Parser", layout="wide")

st.title("ECI PDF Parser & ASDD Annexure Generator")
st.write("Upload a vector PDF generated from ECI databases to dynamically build and export specialized ASDD Annexure reports.")

# Check for persistently saved PDF dataset
if st.session_state['voter_df'] is None:
    cached_df, cached_ac, cached_part, cached_fn = load_cached_data()
    if cached_df is not None:
        st.session_state['voter_df'] = cached_df
        st.session_state['ac_info'] = cached_ac
        st.session_state['part_info'] = cached_part
        st.session_state['pdf_filename'] = cached_fn

# 1. File Upload Selector
uploaded_file = st.file_uploader("Upload ECI Enumeration Form PDF File", type=["pdf"])

if uploaded_file is not None:
    if uploaded_file.name != st.session_state['pdf_filename']:
        try:
            with st.spinner("Reading ECI PDF layers..."):
                file_bytes = uploaded_file.read()
                df, parsed_ac, parsed_part = parse_eci_pdf(file_bytes)
                
                if df.empty:
                    st.error("No valid voter records could be extracted. Please check that this is a vector text PDF containing tabular voter data.")
                else:
                    st.session_state['voter_df'] = df
                    st.session_state['ac_info'] = parsed_ac
                    st.session_state['part_info'] = parsed_part
                    st.session_state['pdf_filename'] = uploaded_file.name
                    save_to_cache(df, parsed_ac, parsed_part, uploaded_file.name)
                    st.success("Successfully parsed and saved voter database.")
        except Exception as e:
            st.error(f"Parsing failed: {e}")

# If dataset is active, display report configuration interfaces
if st.session_state['voter_df'] is not None:
    voter_db = st.session_state['voter_df']
    
    # Render Status Block
    col_status, col_clear = st.columns([4, 1])
    with col_status:
        st.info(f"📄 **Active File:** `{st.session_state['pdf_filename']}` | **AC Info:** {st.session_state['ac_info']} | **Part Number:** {st.session_state['part_info']}")
    with col_clear:
        if st.button("🗑️ Clear Parsed Data", use_container_width=True, help="Removes the persistent cache and resets the app."):
            clear_cache()
            
    st.markdown("---")
    st.subheader("Category-wise Voter Sublists & Download Formats")
    st.write("Review, edit, and export specialized voter lists below based on ECI uncollectable reasons.")
    
    # Build 5 tab categories
    tab_list = list(PDF_CATEGORIES.keys())
    tabs = st.tabs(tab_list)
    
    for i, cat_name in enumerate(tab_list):
        with tabs[i]:
            cat_config = PDF_CATEGORIES[cat_name]
            
            # Filter rows belonging to the specific category
            cat_df = voter_db[voter_db['category'] == cat_name].copy()
            
            if not cat_df.empty:
                st.write(f"📁 Found **{len(cat_df)}** records matching **{cat_name}**.")
                
                # Setup editable table structure with custom category default remarks
                cat_df['remarks'] = cat_config['default_remark']
                
                display_schema = {
                    'serial_no': 'SL No. in the Part',
                    'epic_no': 'EPIC No.',
                    'elector_name': 'Name of the Elector',
                    'relative_name': 'Name of Relative',
                    'remarks': cat_config['last_col']
                }
                
                # Keep only display columns
                editable_subset = cat_df[list(display_schema.keys())].rename(columns=display_schema)
                
                # Render Data Editor
                editor_key = f"edit_{cat_name}_{st.session_state['pdf_filename']}_{len(cat_df)}"
                edited_df = st.data_editor(editable_subset, use_container_width=True, hide_index=True, key=editor_key)
                
                # Format final row payloads back into ReportLab
                payload_rows = []
                for _, row in edited_df.iterrows():
                    payload_rows.append({
                        'serial_no': row['SL No. in the Part'],
                        'epic_no': row['EPIC No.'],
                        'elector_name': row['Name of the Elector'],
                        'relative_name': row['Name of Relative'],
                        'remarks': row[cat_config['last_col']]
                    })
                
                # Create ReportLab export buffer
                pdf_report_buffer = generate_pdf_report(
                    payload_rows, 
                    st.session_state['ac_info'], 
                    st.session_state['part_info'], 
                    cat_config
                )
                
                filename = f"{cat_config['annexure']}_{cat_config['filename_suffix']}.pdf"
                
                # Download button specifically for this subset
                st.download_button(
                    label=f"📄 Download {cat_config['annexure']} ({cat_name}) PDF",
                    data=pdf_report_buffer,
                    file_name=filename,
                    mime="application/pdf",
                    key=f"dl_{cat_name}"
                )
                
            else:
                st.info(f"No records mapped to the '{cat_name}' category in this document.")
else:
    st.info("Upload an ECI Enumeration Form PDF file using the file uploader above to begin processing.")
