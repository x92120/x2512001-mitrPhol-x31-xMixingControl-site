
import sys
import os

# Add the FastAPI directory to sys.path
sys.path.append("/home/x92120/xApp/x01-mitrPhol/x01-localApp/x02-BackEnd/x0201-fastAPI")

import crud
import models
import schemas
from database import SessionLocal

def create_app_user():
    db = SessionLocal()
    try:
        # Check if user exists
        db_user = crud.get_user_by_username(db, "user-001")
        if db_user:
            print("Database user user-001 already exists.")
            return

        # Create user schema
        # Since "user" is not a valid role in the Enum, I will try "Operator" 
        # but I will also see if I can force "user" if the user really wants it.
        # But looking at models.py, it is a strict Enum.
        
        user_in = schemas.UserCreate(
            username="user-001",
            email="user-001@example.com", # Default email
            full_name="User 001",
            role="Operator", # Using Operator as a safe default
            password="mitrphol100x",
            status="Active"
        )
        
        new_user = crud.create_user(db, user_in)
        print(f"Database user created: {new_user.username} with role {new_user.role}")
    except Exception as e:
        print(f"Error creating database user: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_app_user()
