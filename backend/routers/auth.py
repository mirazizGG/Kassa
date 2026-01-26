from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from typing import List

from database import get_db, Employee
from schemas import Token, EmployeeCreate, EmployeeOut, EmployeeUpdate
from core import verify_password, get_password_hash, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(Employee).where(Employee.username == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": user.role,
        "permissions": user.permissions,
        "username": user.username
    }

@router.post("/employees", response_model=EmployeeOut)
async def create_employee(
    user: EmployeeCreate, 
    current_user: Employee = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create employees")
    
    hashed_password = get_password_hash(user.password)
    db_user = Employee(
        username=user.username,
        hashed_password=hashed_password,
        role=user.role,
        permissions=user.permissions,
        full_name=user.full_name,
        phone=user.phone,
        address=user.address,
        passport=user.passport,
        notes=user.notes
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.get("/employees", response_model=List[EmployeeOut])
async def get_employees(
    current_user: Employee = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view employee list")
    
    from sqlalchemy import select
    result = await db.execute(select(Employee))
    return result.scalars().all()
