from server.db import get_connection, init_db

RESTAURANTS = [
    ("The Golden Spoon", "American", "12 Main St"),
    ("Sakura Sushi", "Japanese", "88 Cherry Blossom Ave"),
    ("Trattoria Bella", "Italian", "45 Vine St"),
    ("Taco Verde", "Mexican", "210 Sunset Blvd"),
    ("Curry House", "Indian", "77 Spice Rd"),
    ("Le Petit Bistro", "French", "5 Rue de Paris"),
]


def seed():
    init_db()
    conn = get_connection()
    existing = conn.execute("SELECT COUNT(*) AS c FROM restaurants").fetchone()["c"]
    if existing == 0:
        conn.executemany(
            "INSERT INTO restaurants (name, cuisine, address) VALUES (?, ?, ?)",
            RESTAURANTS,
        )
        conn.commit()
        print(f"Seeded {len(RESTAURANTS)} restaurants.")
    else:
        print(f"Restaurants table already has {existing} rows, skipping seed.")
    conn.close()


if __name__ == "__main__":
    seed()
