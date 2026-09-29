from sqlalchemy import text
from database import engine

def create_table():
    with engine.connect() as conn:
        print("Creating table 'intake_package_receive' if not exists...")
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS intake_package_receive (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    intake_list_id INT NOT NULL,
                    package_no INT NOT NULL,
                    weight FLOAT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(50),
                    INDEX (intake_list_id),
                    FOREIGN KEY (intake_list_id) REFERENCES ingredient_intake_lists(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """))
            conn.commit()
            print("Successfully checked/created table intake_package_receive.")
        except Exception as e:
            print(f"Error creating table: {e}")

if __name__ == "__main__":
    create_table()
