"""
Phase 2 Validation Tests
Quick checks to verify MVP foundation is correctly set up.
"""

import os
import sys
import json
from pathlib import Path


def test_structure():
    """Verify project structure is in place."""
    print("✓ Testing Project Structure...")
    
    required_dirs = {
        "backend/app": ["api", "core", "db", "models", "schemas", "services"],
        "backend/tests": [],
        "frontend/src": ["components", "hooks", "services"],
        "frontend/public": [],
        "storage": [],
        "docs": [],
    }
    
    root = Path(__file__).parent
    
    for dir_path, subdirs in required_dirs.items():
        full_path = root / dir_path
        assert full_path.is_dir(), f"Missing directory: {dir_path}"
        print(f"  ✓ {dir_path}/")
        
        for subdir in subdirs:
            sub_path = full_path / subdir
            assert sub_path.exists(), f"Missing subdirectory: {dir_path}/{subdir}"
            print(f"    ✓ {subdir}/")


def test_backend_files():
    """Verify backend Python files exist."""
    print("\n✓ Testing Backend Files...")
    
    required_files = {
        "backend/app/__init__.py": True,
        "backend/app/main.py": True,
        "backend/app/config.py": True,
        "backend/app/core/exceptions.py": True,
        "backend/app/db/database.py": True,
        "backend/app/api/health.py": True,
        "backend/requirements.txt": True,
        "backend/pytest.ini": True,
        "backend/tests/conftest.py": True,
        "backend/tests/test_health.py": True,
    }
    
    root = Path(__file__).parent
    
    for file_path, should_exist in required_files.items():
        full_path = root / file_path
        if should_exist:
            assert full_path.exists(), f"Missing file: {file_path}"
            assert full_path.stat().st_size > 0, f"Empty file: {file_path}"
            print(f"  ✓ {file_path}")
        else:
            if full_path.exists():
                print(f"  ⚠ Unexpected file: {file_path}")


def test_frontend_files():
    """Verify frontend files exist."""
    print("\n✓ Testing Frontend Files...")
    
    required_files = {
        "frontend/package.json": True,
        "frontend/tsconfig.json": True,
        "frontend/vite.config.ts": True,
        "frontend/index.html": True,
        "frontend/src/main.tsx": True,
        "frontend/src/App.tsx": True,
        "frontend/src/globals.css": True,
        "frontend/tailwind.config.js": True,
        "frontend/postcss.config.js": True,
        "frontend/src/services/api.ts": True,
        "frontend/src/hooks/useApi.ts": True,
        "frontend/src/components/HealthStatus.tsx": True,
    }
    
    root = Path(__file__).parent
    
    for file_path, should_exist in required_files.items():
        full_path = root / file_path
        if should_exist:
            assert full_path.exists(), f"Missing file: {file_path}"
            assert full_path.stat().st_size > 0, f"Empty file: {file_path}"
            print(f"  ✓ {file_path}")


def test_config():
    """Verify configuration files exist."""
    print("\n✓ Testing Configuration Files...")
    
    root = Path(__file__).parent
    
    # Check .env.example
    env_example = root / ".env.example"
    assert env_example.exists(), "Missing .env.example"
    print(f"  ✓ .env.example")
    
    # Check .gitignore
    gitignore = root / ".gitignore"
    assert gitignore.exists(), "Missing .gitignore"
    content = gitignore.read_text()
    assert "backend/.venv/" in content, ".gitignore missing backend patterns"
    assert "frontend/node_modules/" in content, ".gitignore missing frontend patterns"
    print(f"  ✓ .gitignore (with backend & frontend patterns)")


def test_wan2gp_integrity():
    """Verify Wan2GP engine is untouched."""
    print("\n✓ Testing Wan2GP Integrity...")
    
    root = Path(__file__).parent
    
    required_engine_files = {
        "wgp.py": True,
        "requirements.txt": True,
        "shared": True,
        "models": True,
        "defaults": True,
    }
    
    for file_path, should_exist in required_engine_files.items():
        full_path = root / file_path
        if should_exist:
            assert full_path.exists(), f"Wan2GP missing: {file_path}"
            print(f"  ✓ {file_path}")


def test_dependencies():
    """Verify dependency lists are complete."""
    print("\n✓ Testing Dependencies...")
    
    root = Path(__file__).parent
    
    # Backend requirements
    backend_req = (root / "backend/requirements.txt").read_text()
    required_deps = ["fastapi", "uvicorn", "sqlalchemy", "pydantic", "pytest"]
    for dep in required_deps:
        assert dep.lower() in backend_req.lower(), f"Missing dependency: {dep}"
        print(f"  ✓ Backend: {dep}")
    
    # Frontend package.json
    package_json = (root / "frontend/package.json").read_text()
    package_data = json.loads(package_json)
    required_frontend = ["react", "typescript", "vite", "tailwindcss"]
    for dep in required_frontend:
        assert dep in str(package_data.get("dependencies", {})) or \
               dep in str(package_data.get("devDependencies", {})), \
               f"Missing frontend dependency: {dep}"
        print(f"  ✓ Frontend: {dep}")


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Wan2GP Platform - Phase 2 MVP Foundation Validation")
    print("=" * 60)
    
    try:
        test_structure()
        test_backend_files()
        test_frontend_files()
        test_config()
        test_wan2gp_integrity()
        test_dependencies()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - Foundation is ready!")
        print("=" * 60)
        print("\nNext Steps:")
        print("1. Backend: pip install -r requirements.txt && python -m uvicorn app.main:app --reload")
        print("2. Frontend: npm install && npm run dev")
        print("3. Verify: curl http://localhost:8000/api/v1/health")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
