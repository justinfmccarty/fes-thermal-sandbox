"""Material-inspired CSS injected into the Streamlit app."""

MATERIAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Roboto', sans-serif;
}

.material-card {
    background: #FFFFFF;
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08);
}

.material-header {
    color: #1976D2;
    font-weight: 500;
    font-size: 1.35rem;
    margin-bottom: 0.5rem;
}

.status-ok { color: #2E7D32; font-weight: 500; }
.status-missing { color: #C62828; font-weight: 500; }
.status-warning { color: #F57C00; font-weight: 500; }
.status-running { color: #1565C0; font-weight: 500; }

.stButton > button[kind="primary"] {
    background-color: #1976D2;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 500;
}
</style>
"""
