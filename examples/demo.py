"""
FastAPI SaaS Demo: Shows the complete API structure and simulates CRUD operations.
Run: python examples/demo.py

For the full API with Swagger UI:
  pip install -r requirements.txt
  python -m uvicorn app.main:create_app --factory --reload
  Open http://localhost:8000/docs
"""
import json, datetime, hashlib, uuid

# Simulated database
_db = {"users": [], "tenants": []}

def create_tenant(name: str, plan: str = "free") -> dict:
    tenant = {"id": str(uuid.uuid4())[:8], "name": name, "plan": plan, "created_at": datetime.datetime.now().isoformat()}
    _db["tenants"].append(tenant)
    return tenant

def create_user(email: str, name: str, tenant_id: str, role: str = "member") -> dict:
    user = {
        "id": str(uuid.uuid4())[:8], "email": email, "name": name,
        "tenant_id": tenant_id, "role": role, "is_active": True,
        "created_at": datetime.datetime.now().isoformat(),
    }
    _db["users"].append(user)
    return user

def login(email: str, password: str) -> dict:
    user = next((u for u in _db["users"] if u["email"] == email), None)
    if not user: return {"error": "Invalid credentials"}
    token = hashlib.sha256(f"{email}:{password}".encode()).hexdigest()[:32]
    return {"access_token": token, "token_type": "bearer", "user": user}

def list_users(tenant_id: str) -> list:
    return [u for u in _db["users"] if u["tenant_id"] == tenant_id]

def update_user_role(user_id: str, role: str) -> dict:
    user = next((u for u in _db["users"] if u["id"] == user_id), None)
    if user: user["role"] = role
    return user

def get_subscription(tenant_id: str) -> dict:
    tenant = next((t for t in _db["tenants"] if t["id"] == tenant_id), None)
    return {"tenant": tenant["name"], "plan": tenant["plan"], "status": "active", "current_period_end": "2026-05-01"}

def main():
    print("🚀 FastAPI SaaS Demo (simulated, no server needed)")
    print("=" * 55)
    print("Endpoints: /auth/register, /auth/login, /users, /billing/subscription")
    
    # Create tenant
    print("\n📌 POST /auth/register — Create tenant + admin user")
    tenant = create_tenant("Acme Corp", "pro")
    admin = create_user("admin@acme.com", "Sarah Chen", tenant["id"], "admin")
    print(f"   Tenant: {json.dumps(tenant)}")
    print(f"   Admin: {json.dumps(admin)}")
    
    # Login
    print("\n📌 POST /auth/login")
    token = login("admin@acme.com", "demo123")
    print(f"   Token: {json.dumps(token, indent=2)}")
    
    # Create team members
    print("\n📌 POST /users — Add team members")
    for name, email in [("James Wilson", "james@acme.com"), ("Emily Park", "emily@acme.com")]:
        user = create_user(email, name, tenant["id"])
        print(f"   Created: {user['name']} ({user['email']})")
    
    # List users
    print("\n📌 GET /users — List all team members")
    users = list_users(tenant["id"])
    print(f"   {len(users)} users in tenant '{tenant['name']}':")
    for u in users:
        print(f"     {u['name']} ({u['role']})")
    
    # Update role
    print("\n📌 PATCH /users/{id}/role — Promote user")
    updated = update_user_role(users[1]["id"], "admin")
    print(f"   {updated['name']} → {updated['role']}")
    
    # Billing
    print("\n📌 GET /billing/subscription")
    sub = get_subscription(tenant["id"])
    print(f"   {json.dumps(sub, indent=2)}")
    
    print("\n✅ Full CRUD cycle complete — auth, users, billing all working")

if __name__ == "__main__":
    main()
