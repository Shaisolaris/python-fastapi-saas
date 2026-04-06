"""
Demo: Start the API with SQLite and seed data — zero config needed.
Run: python examples/demo.py

Then open http://localhost:8000/docs for Swagger UI.
"""
import sys, os, uvicorn
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Override to SQLite for demo
os.environ.setdefault("DATABASE_URL", "sqlite:///./demo.db")
os.environ.setdefault("SECRET_KEY", "demo-secret-key-not-for-production")
os.environ.setdefault("DEMO_MODE", "true")

def seed_demo_data():
    """Create demo users and data in SQLite."""
    from app.core.database import engine, SessionLocal, Base
    from app.models.user import User
    from app.core.security import hash_password
    
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    if db.query(User).count() == 0:
        users = [
            User(email="admin@demo.com", name="Sarah Chen", hashed_password=hash_password("demo123"), role="admin", is_active=True),
            User(email="user@demo.com", name="James Wilson", hashed_password=hash_password("demo123"), role="member", is_active=True),
        ]
        db.add_all(users)
        db.commit()
        print("🌱 Seeded 2 demo users:")
        print("   admin@demo.com / demo123 (admin)")
        print("   user@demo.com / demo123 (member)")
    
    db.close()

if __name__ == "__main__":
    print("🚀 FastAPI SaaS Demo")
    print("=" * 40)
    seed_demo_data()
    print("\n📄 Swagger UI: http://localhost:8000/docs")
    print("📄 ReDoc: http://localhost:8000/redoc")
    uvicorn.run("app.main:create_app", host="0.0.0.0", port=8000, reload=True, factory=True)
