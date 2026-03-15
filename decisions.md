
- FR = Funcitonal Requirements
- QR = Quality Requirments (non funcitonal)
- UI 

## General FR:
### G-FR: Workflow Provenance
- Log of every Relevant user Event
- user can view the log (sidebar has checkbox that open it as a window rihgt )

### Functionality:
- Reloading a previous analysis from an Export


## General Properties:
### Usability Properties



## Page 0 - 



## FR 1. - Input (Page 1)
different starts to set an input:
### FR 1.1: FASTA Input (string)
### FR 1.2: NCBI GB-ID Requests 
### FR 1.3: possible additional Features:
- Feature: File Upload (FASTA, GenBank)

## FR 2. - Alignment (Page 2)
### Feature: Selection of Alignment Tool
- **General:**
  - transparent settings
  - enable custom settings
- Starting with only MAFFTv5
- 

## Page 3 - Visualization
### Feature: Visualizations
- #### Line Chart: HP Linechart
- #### Line Chart: PR (analog to HP chart)
- #### Bar Chart: Appearing Aminoacids per Position
### FR: Export
- #### FR: analysis session export
  - user dialog that asks for a name for a name for the analysis
    - with preset value: "roiviz_analysis_yyyymmdd.json"
      - Namen mit Nina und Amir abstimmen
- #### FR: Provenance Export
- as ZIP file
- Export of the computed profiles as CSV
  - Inputs and Alignments
    - Cols: 
      - input_type (fasta, ?user-input?, genbank file, genbank id)
      - input_raw: fasta, gb etc
      - ncbi_timestamp: for fetched data
      - selected_mat_peptide:(for gb records/ fetching) 
      - alignment_tool (only name or more info?)
      - 
  - HP Profiles
    - alignment a (betternames??)
    - alignment b 
    - algmnt_a_aa
  - PR Profiles
  - AA Frequency per Position
- Export of the Workflow Provenance (.md ??)
- Export of Quick Summary (PDF)
  - Timestamp YYYY.MM.DD HH:mm:SS  
  - Amount of Inputs
    - and what type of input
  - Used Alignment tool (and Version)
  - Notes/ Annotations
    - amino acid annotations grouped by aa only for aa that had annoatations
    - Regional Annotations: Rendered on the PDF? 
  - MAYBE IF NOT OVERKILL:
    - inlcude the Charts in the Report (in landscape?)
- Low prio: custom Export settings
  - what export to inlcude
  - CSV (comma, semicolon)
  - offer TSV?


## Data 

# Random:
- bar or plot? 
- choose structure how to write my requimrents chapter
  - 