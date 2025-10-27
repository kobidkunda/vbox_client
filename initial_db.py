import logging
from app.db.session import engine
from app.models.lead import Base # Import the Base from your model file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db() -> None:
    try:
        logger.info("Creating all database tables...")
        # The create_all method inspects the Base for all declarative classes
        # (like your Lead model) and creates the corresponding tables in the database.
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

if __name__ == "__main__":
    init_db()