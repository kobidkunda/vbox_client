import os
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import distinct

from app.db.session import SessionLocal
from app.crud import lead as lead_crud
from app.models.lead import Lead

# --- START: ROBUST TEMPLATE PATH DISCOVERY & LOGGING ---
# Configure logging to be more visible
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the absolute path of the directory where this file (frontend.py) is located.
# e.g., /home/user/project/app/api/v1/endpoints
current_dir = os.path.dirname(os.path.abspath(__file__))

# Construct the absolute path to the project's root directory.
# We navigate up four levels from the current file's location.
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))

# Construct the absolute path to the 'templates' directory.
templates_dir = os.path.join(project_root, "templates")

# --- CRITICAL LOGGING ---
# Print the paths to the console so we know exactly what is being used.
logger.info(f"PROJECT ROOT calculated as: {project_root}")
logger.info(f"TEMPLATES DIRECTORY calculated as: {templates_dir}")

# Check if the templates directory actually exists at that path.
if not os.path.isdir(templates_dir):
    logger.error("FATAL: The calculated templates directory does not exist!")
    # If the directory doesn't exist, we can't proceed.
    # This will cause an error on startup, which is better than failing silently.
    raise FileNotFoundError(f"Templates directory not found at: {templates_dir}")
else:
    logger.info("SUCCESS: Templates directory found.")

# Initialize Jinja2Templates with the confirmed absolute path.
templates = Jinja2Templates(directory=templates_dir)
# --- END: ROBUST TEMPLATE PATH DISCOVERY & LOGGING ---


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", tags=["Frontend"], include_in_schema=False)
async def read_main(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("index.html", {"request": request, "voice_groups": lead_crud.get_all_voice_groups(db=db)})

@router.get("/dashboard", tags=["Frontend"], include_in_schema=False)
async def read_dashboard(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("dashboard.html", {"request": request, "leads": lead_crud.get_leads(db=db, limit=500)})

@router.get("/voices", tags=["Frontend"], include_in_schema=False)
async def read_voices_dashboard(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("voices.html", {"request": request, "groups": lead_crud.get_all_voice_groups_with_voices(db=db)})

@router.get("/export", tags=["Frontend"], include_in_schema=False)
async def read_export_page(request: Request, db: Session = Depends(get_db)):
    # Check if the specific template file exists before trying to render it.
    export_template_path = os.path.join(templates_dir, "export.html")
    if not os.path.exists(export_template_path):
        logger.error(f"FATAL: The template file 'export.html' does not exist at: {export_template_path}")
        # Return an error instead of a blank page.
        return {"error": f"Template file not found at {export_template_path}"}, 500

    results = db.query(distinct(Lead.generation_no)).filter(Lead.generation_no.isnot(None)).order_by(Lead.generation_no).all()
    generation_numbers = [res[0] for res in results]
    logger.info(f"DATABASE QUERY: Found generation numbers: {generation_numbers}")
    
    return templates.TemplateResponse("export.html", {"request": request, "generation_numbers": generation_numbers})

# Add this function to your frontend.py file

@router.get("/importer", tags=["Frontend"], include_in_schema=False)
async def read_importer_page(request: Request):
    return templates.TemplateResponse("importer.html", {"request": request})