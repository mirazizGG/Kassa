from main import app

print("=== Barcha API Endpointlar ===\n")
for route in app.routes:
    if hasattr(route, 'methods') and hasattr(route, 'path'):
        methods = ', '.join(route.methods)
        print(f"{methods:10} {route.path}")
