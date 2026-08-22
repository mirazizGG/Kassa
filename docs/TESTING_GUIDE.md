# Testing Guide - Kassa POS System

This guide provides instructions for setting up and running tests for the Kassa POS system.

## Table of Contents
- [Frontend Testing](#frontend-testing)
- [Backend Testing](#backend-testing)
- [Manual Testing Checklist](#manual-testing-checklist)
- [Recommended Testing Tools](#recommended-testing-tools)

---

## Frontend Testing

### Setup Jest and React Testing Library

1. **Install Testing Dependencies**
```bash
cd frontend
npm install --save-dev @testing-library/react @testing-library/jest-dom @testing-library/user-event jest jest-environment-jsdom @vitejs/plugin-react
```

2. **Create Jest Configuration** (`frontend/jest.config.js`)
```javascript
export default {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
  transform: {
    '^.+\\.(js|jsx)$': ['babel-jest', { presets: ['@babel/preset-env', '@babel/preset-react'] }],
  },
};
```

3. **Create Setup File** (`frontend/src/setupTests.js`)
```javascript
import '@testing-library/jest-dom';
```

4. **Update package.json**
```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  }
}
```

### Sample Component Tests

**Example: Login Component Test** (`frontend/src/pages/__tests__/Login.test.jsx`)
```javascript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Login from '../Login';

describe('Login Component', () => {
  test('renders login form', () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    expect(screen.getByPlaceholderText(/admin/i)).toBeInTheDocument();
    expect(screen.getByText(/Tizimga kirish/i)).toBeInTheDocument();
  });

  test('shows error on invalid credentials', async () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const usernameInput = screen.getByPlaceholderText(/admin/i);
    const passwordInput = screen.getByPlaceholderText(/••••••••/i);
    const submitButton = screen.getByText(/Tizimga kirish/i);

    fireEvent.change(usernameInput, { target: { value: 'wrong' } });
    fireEvent.change(passwordInput, { target: { value: 'wrong' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Xatolik/i)).toBeInTheDocument();
    });
  });
});
```

### E2E Testing with Playwright

1. **Install Playwright**
```bash
cd frontend
npm install --save-dev @playwright/test
npx playwright install
```

2. **Create Playwright Config** (`frontend/playwright.config.js`)
```javascript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  },
});
```

3. **Sample E2E Test** (`frontend/e2e/login.spec.js`)
```javascript
import { test, expect } from '@playwright/test';

test('login flow', async ({ page }) => {
  await page.goto('/login');

  await page.fill('input[placeholder="admin"]', 'admin');
  await page.fill('input[type="password"]', '123');
  await page.click('button:has-text("Tizimga kirish")');

  await expect(page).toHaveURL('/');
  await expect(page.locator('h1')).toContainText('Asosiy Ko\'rsatkichlar');
});

test('theme switching works', async ({ page }) => {
  await page.goto('/login');

  // Find and click theme toggle
  await page.click('[aria-label="Toggle theme"]');

  // Verify dark mode is applied
  const htmlElement = page.locator('html');
  await expect(htmlElement).toHaveClass(/dark/);
});
```

4. **Run E2E Tests**
```bash
npx playwright test
npx playwright test --ui  # Interactive mode
npx playwright show-report  # View test report
```

---

## Backend Testing

### Setup Pytest

1. **Install Testing Dependencies**
```bash
cd backend
pip install pytest pytest-asyncio httpx pytest-cov
```

2. **Create Pytest Configuration** (`backend/pytest.ini`)
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

3. **Create Test Database Fixture** (`backend/tests/conftest.py`)
```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient
from main import app
from database import Base, get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

@pytest.fixture
async def test_db():
    # Create test database
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestingSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def client(test_db):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

### Sample Backend Tests

**Example: Auth Tests** (`backend/tests/test_auth.py`)
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # First create a user
    response = await client.post("/auth/token", data={
        "username": "admin",
        "password": "123"
    })

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    response = await client.post("/auth/token", data={
        "username": "wrong",
        "password": "wrong"
    })

    assert response.status_code == 401

@pytest.mark.asyncio
async def test_protected_route_without_token(client: AsyncClient):
    response = await client.get("/inventory/products")
    assert response.status_code == 401
```

**Example: POS Tests** (`backend/tests/test_pos.py`)
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_open_shift(client: AsyncClient, auth_token):
    response = await client.post(
        "/pos/shifts/open",
        json={"opening_balance": 0, "note": "Test shift"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "open"

@pytest.mark.asyncio
async def test_create_sale_without_open_shift(client: AsyncClient, auth_token):
    response = await client.post(
        "/pos/sales",
        json={
            "total_amount": 100000,
            "payment_method": "cash",
            "items": []
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 400
    assert "smena" in response.json()["detail"].lower()
```

4. **Run Backend Tests**
```bash
cd backend
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest --cov=.                  # With coverage
pytest tests/test_auth.py       # Specific file
pytest -k "test_login"          # Tests matching pattern
```

---

## Manual Testing Checklist

### 1. Authentication & Authorization
- [ ] Login with valid credentials (admin/123)
- [ ] Login with invalid credentials shows error
- [ ] Logout clears session
- [ ] Token expiration redirects to login (wait 10 hours or manually test)
- [ ] Admin can access all pages
- [ ] Manager cannot access employee management
- [ ] Cashier has limited access

### 2. Dark/Light Theme
- [ ] Theme toggle works on login page
- [ ] Theme persists after page reload
- [ ] All pages display correctly in dark mode
- [ ] All pages display correctly in light mode
- [ ] Text is readable in both themes
- [ ] Buttons and interactive elements visible in both themes

### 3. Dashboard
- [ ] Statistics load correctly
- [ ] Navigation buttons work
- [ ] Recent sales table displays data
- [ ] Quick action buttons navigate correctly

### 4. POS (Point of Sale)
- [ ] Cannot make sales without opening shift
- [ ] Can open shift successfully
- [ ] Search for products works
- [ ] Add products to cart
- [ ] Update quantities in cart
- [ ] Remove items from cart
- [ ] Select payment method (cash/card/credit)
- [ ] Select client for credit sales
- [ ] Complete sale successfully
- [ ] Cart clears after sale
- [ ] Can close shift with correct balance

### 5. Inventory
- [ ] View all products
- [ ] Search products by name
- [ ] Search products by barcode
- [ ] Add new product (manager/admin only)
- [ ] Edit existing product
- [ ] Delete product (shows confirmation)
- [ ] Low stock warning displays correctly
- [ ] Product form validation works

### 6. CRM (Customers)
- [ ] View all clients
- [ ] Search clients by name
- [ ] Search clients by phone
- [ ] Add new client
- [ ] View client balance (debt/prepayment)
- [ ] Process debt payment
- [ ] View payment history

### 7. Finance
- [ ] View sales statistics
- [ ] View expenses
- [ ] Add new expense
- [ ] Delete expense (manager/admin only)
- [ ] Statistics calculate correctly

### 8. Employees
- [ ] View all employees (manager/admin)
- [ ] Add new employee (admin only)
- [ ] Edit employee (admin only)
- [ ] View tasks
- [ ] Create new task
- [ ] Assign task to employee

### 9. Error Handling
- [ ] API errors show toast notifications
- [ ] 401 errors redirect to login
- [ ] Network errors display properly
- [ ] Form validation errors show clearly
- [ ] Error boundary catches React errors

### 10. Responsive Design
- [ ] Works on desktop (1920x1080)
- [ ] Works on laptop (1366x768)
- [ ] Works on tablet (768x1024)
- [ ] Works on mobile (375x667)
- [ ] Sidebar collapses on small screens

---

## Recommended Testing Tools

### Frontend
- **Jest** - Unit testing framework
- **React Testing Library** - Component testing
- **Playwright** - E2E testing (recommended)
- **Cypress** - Alternative E2E testing
- **MSW (Mock Service Worker)** - API mocking
- **axe-core** - Accessibility testing

### Backend
- **pytest** - Testing framework
- **pytest-asyncio** - Async test support
- **httpx** - Async HTTP client for testing
- **pytest-cov** - Coverage reporting
- **factory-boy** - Test data factories
- **Faker** - Generate fake data

### Code Quality
- **ESLint** - JavaScript linting (already configured)
- **Prettier** - Code formatting
- **Black** - Python code formatting
- **flake8** - Python linting
- **mypy** - Python type checking

### Performance
- **Lighthouse** - Web performance audit
- **React DevTools Profiler** - React performance
- **Chrome DevTools** - Network and performance

### API Testing
- **Postman** - Manual API testing
- **Insomnia** - Alternative to Postman
- **Thunder Client** - VS Code extension

---

## CI/CD Integration (Future)

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: cd frontend && npm install
      - run: cd frontend && npm test
      - run: cd frontend && npx playwright install
      - run: cd frontend && npx playwright test

  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: cd backend && pip install -r requirements.txt
      - run: cd backend && pip install pytest pytest-asyncio httpx pytest-cov
      - run: cd backend && pytest --cov
```

---

## Coverage Goals

### Target Coverage Metrics
- **Frontend**: 70%+ code coverage
- **Backend**: 80%+ code coverage
- **E2E**: Critical user flows covered

### Priority Testing Areas
1. Authentication & Authorization (critical)
2. Payment processing (critical)
3. Inventory management (high)
4. Sales transactions (high)
5. Client management (medium)
6. Reporting (medium)

---

## Quick Start Testing

```bash
# Frontend
cd frontend
npm install --save-dev @playwright/test
npx playwright install
npx playwright test

# Backend
cd backend
pip install pytest pytest-asyncio httpx
pytest -v

# Run both
npm test && pytest
```

---

For questions or contributions to the testing infrastructure, please refer to the main README.md or open an issue.
