import sqlite3
import os

db_path = "database/engine.db"  # Ajusta la ruta si tu sqlite está en otra ubicación

def seed():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Asegúrate de que la tabla credentials exista o adapta según tus modelos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY,
            username TEXT,
            encrypted_password TEXT,
            email TEXT,
            encrypted_api_key TEXT
        )
    """)
    
    for i in range(1, 9):
        cursor.execute("""
            INSERT OR REPLACE INTO credentials (id, username, encrypted_password, email, encrypted_api_key)
            VALUES (?, ?, ?, ?, ?)
        """, (i, f"user{i}@streaming.com", "password123", "grandezsalas192@gmail.com", "apikey123"))
    
    conn.commit()
    conn.close()
    print("✅ Credenciales locales de prueba insertadas con éxito.")

if __name__ == "__main__":
    seed()