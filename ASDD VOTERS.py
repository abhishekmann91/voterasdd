import streamlit as st
import pandas as pd
import io
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Define category properties per the system specification
CATEGORIES = {
    "Category 1: Permanently Shifted (Annexure-II)": {
        "annexure": "Annexure-II",
        "title": "List of ASDD Electors: Category - Permanently Shifted",
        "last_col": "Category / Remarks",
        "default_remark": "Permanently Shifted"
    },
    "Category 2: Dead / Death Cases (Annexure-III)": {
        "annexure": "Annexure-III",
        "title": "List of ASDD Electors: Category - Dead / Death Cases",
        "last_col": "Category / Remarks",
        "default_remark": "Dead"
    },
    "Category 3: Duplicate / Already Enrolled (Annexure-IV)": {
        "annexure": "Annexure-IV",
        "title": "List of ASDD Electors: Category - Duplicate / Already Enrolled",
        "last_col": "Category / Remarks",
        "default_remark": "Duplicate"
    },
    "Category 4: Others (Includes Absent, Refused to sign, etc.) (Annexure-V)": {
        "annexure": "Annexure-V",
        "title": "List of ASDD Electors: Category - Others",
        "last_col": "Remarks (Refused to sign etc.)",
        "default_remark": "Absent / Refused to Sign"
    }
}

def clean_val(val):
    if pd.isna(val) or val is None:
        return ""
    # Convert float representation of numbers like 12.0 to 12
    v_str = str(val).strip()
    return re.sub(r'\.0$', '', v_str)

def normalize_columns(df):
    """Maps dynamic column names from the uploaded sheet to standardized internally-used key names."""
    mapping = {
        'assembly constituency (ac) no. & name': 'ac_name',
        'assembly constituency': 'ac_name',
        'ac name': 'ac_name',
        'part no.': 'part_no',
        'part no': 'part_no',
        'part number': 'part_no',
        'part serial no.': 'serial_no',
        'part serial no': 'serial_no',
        'sl no. in the part': 'serial_no',
        'sl no': 'serial_no',
        'epic no.': 'epic_no',
        'epic no': 'epic_no',
        'epic number': 'epic_no',
        'elector name': 'elector_name',
        'name of the elector': 'elector_name',
        'name': 'elector_name',
        'relative name': 'relative_name',
        'name of relative': 'relative_name'
    }
    rename_dict = {}
    for col in df.columns:
        normalized = str(col).strip().lower()
        if normalized in mapping:
            rename_dict[col] = mapping[normalized]
    return df.rename(columns=rename_dict)

def generate_pdf(data_rows, ac_name, part_no, category_info):
    """Generates standard A4 PDF containing headers, matched records table, and formatted signature blocks."""
    buffer = io.BytesIO()
    # A4 printable area is roughly 523pt wide with 36pt (0.5 inch) margins
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

    # Define clean typography styles
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

    # 1. Header Sections
    story.append(Paragraph(category_info['annexure'], style_annexure))
    story.append(Paragraph(f"AC No. & Name: {ac_name} | Part No.: {part_no}", style_header))
    story.append(Paragraph(category_info['title'], style_title))

    # 2. Setup Main Voter Data Table
    table_headers = [
        Paragraph("<b>S. No.</b>", style_cell_bold),
        Paragraph("<b>EPIC No.</b>", style_cell_bold),
        Paragraph("<b>SL No. in the Part</b>", style_cell_bold),
        Paragraph("<b>Name of the Elector</b>", style_cell_bold),
        Paragraph("<b>Name of Relative</b>", style_cell_bold),
        Paragraph(f"<b>{category_info['last_col']}</b>", style_cell_bold)
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

    # Standard landscape printable width distribution across 6 columns
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

    # 3. Footer Block (Signatures of BLO & BLA-2)
    footer_table_data = [
        [
            Paragraph("<b>Sign of BLO:</b> _____________________", style_cell),
            Paragraph("<b>Sign of BLA-2:</b>", style_cell)
        ],
        [
            "",
            Paragraph("(i) __________________________", style_cell)
        ],
        [
            "",
            Paragraph("(ii) __________________________", style_cell)
        ],
        [
            "",
            Paragraph("(iii) __________________________", style_cell)
        ],
        [
            "",
            Paragraph("(iv) __________________________", style_cell)
        ]
    ]
    
    # 2-column signature alignment
    footer_table = Table(footer_table_data, colWidths=[240, 283])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    
    # Keep the signature group intact (avoids breaking awkwardly onto new pages)
    story.append(KeepTogether([footer_table]))

    doc.build(story)
    buffer.seek(0)
    return buffer


# --- Streamlit Front-End ---
st.set_page_config(page_title="ASDD PDF Generator", layout="wide")

st.title("Voter List Processing & ASDD PDF Generator")
st.write("This application helps Election Booth Level Officers (BLOs) generate formatted ASDD PDF Annexure reports.")

# 1. Excel File Upload
uploaded_file = st.file_uploader("Upload Master Voter List Excel File (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        # Load raw data safely
        raw_df = pd.read_excel(uploaded_file, dtype=str)
        normalized_df = normalize_columns(raw_df)
        
        # Verify columns exist
        required_cols = ['ac_name', 'part_no', 'serial_no', 'epic_no', 'elector_name', 'relative_name']
        missing_cols = [col for col in required_cols if col not in normalized_df.columns]
        
        if missing_cols:
            st.error(f"The Excel file is missing the following required structural columns: {', '.join(missing_cols)}")
            st.info("Ensure your master Excel file contains: 'Assembly Constituency (AC) No. & Name', 'Part No.', 'Part Serial No.', 'EPIC No.', 'Elector Name', and 'Relative Name'.")
        else:
            # 2. Form Selections
            col1, col2 = st.columns(2)
            
            with col1:
                part_no_selection = st.selectbox(
                    "Select Part Number:",
                    options=["242", "243", "244", "245", "246", "247", "248", "249", "252"]
                )
            
            with col2:
                category_selection = st.selectbox(
                    "Select Target List Category (Annexure Type):",
                    options=list(CATEGORIES.keys())
                )
                
            category_info = CATEGORIES[category_selection]
            
            # Input Text Field for Serial Numbers
            serial_input = st.text_area(
                "Enter Part Serial Numbers (SL No. in the Part):",
                placeholder="Examples: 14, 25, 102 (Separated by commas, spaces, or lines)",
                help="You can copy/paste serial numbers directly."
            )
            
            # Parse entered numbers
            parsed_serials = []
            if serial_input.strip():
                # Regular expression to extract numeric elements
                parsed_serials = [clean_val(s) for s in re.split(r'[,\s\n]+', serial_input) if s.strip()]
            
            # 3. Lookup Records
            if parsed_serials:
                # Standardize database format columns for lookup matching
                normalized_df['part_no_clean'] = normalized_df['part_no'].apply(clean_val)
                normalized_df['serial_no_clean'] = normalized_df['serial_no'].apply(clean_val)
                
                matched_records = normalized_df[
                    (normalized_df['part_no_clean'] == part_no_selection) &
                    (normalized_df['serial_no_clean'].isin(parsed_serials))
                ].copy()
                
                if not matched_records.empty:
                    # Dynamically extract Assembly Constituency Name
                    ac_name_raw = matched_records['ac_name'].iloc[0] if 'ac_name' in matched_records.columns else "N/A"
                    ac_name = clean_val(ac_name_raw) if ac_name_raw else "N/A"
                    
                    st.success(f"Successfully located {len(matched_records)} voter record(s) matching Part No. {part_no_selection}.")
                    
                    # Construct default remark structure
                    matched_records['remarks'] = category_info['default_remark']
                    
                    # Prepare structured dataset for verification & editing
                    display_cols = {
                        'serial_no_clean': 'SL No. in the Part',
                        'epic_no': 'EPIC No.',
                        'elector_name': 'Name of the Elector',
                        'relative_name': 'Name of Relative',
                        'remarks': category_info['last_col']
                    }
                    
                    # Clean records and fill empty cells
                    for col in display_cols.keys():
                        if col not in matched_records.columns:
                            matched_records[col] = ""
                        else:
                            matched_records[col] = matched_records[col].apply(clean_val)
                    
                    editable_df = matched_records[list(display_cols.keys())].rename(columns=display_cols)
                    
                    # Provide interface to directly edit remarks if needed
                    st.subheader("Verify & Edit Report Details")
                    st.write("Double-click cells in the table below to customize fields (such as 'Remarks') before PDF generation.")
                    edited_df = st.data_editor(editable_df, use_container_width=True, hide_index=True)
                    
                    # Transform back to normalized structure for PDF compilation
                    final_pdf_rows = []
                    for _, row in edited_df.iterrows():
                        final_pdf_rows.append({
                            'serial_no': row['SL No. in the Part'],
                            'epic_no': row['EPIC No.'],
                            'elector_name': row['Name of the Elector'],
                            'relative_name': row['Name of Relative'],
                            'remarks': row[category_info['last_col']]
                        })
                    
                    # 4. Generate & Download Action
                    st.markdown("---")
                    pdf_buffer = generate_pdf(final_pdf_rows, ac_name, part_no_selection, category_info)
                    
                    filename = f"{category_info['annexure']}_Part_{part_no_selection}.pdf"
                    
                    st.download_button(
                        label="📄 Generate & Download PDF Report",
                        data=pdf_buffer,
                        file_name=filename,
                        mime="application/pdf"
                    )
                else:
                    st.warning(f"No matching records found for the entered Serial Numbers in Part {part_no_selection}.")
            else:
                st.info("Please enter one or more Serial Numbers to begin processing.")
                
    except Exception as e:
        st.error(f"An error occurred while loading or parsing the Excel file. Details: {e}")
        st.info("Verify your file has the appropriate spreadsheet headers and is not corrupted.")
else:
    st.info("Upload your Excel master file using the uploader above to begin.")