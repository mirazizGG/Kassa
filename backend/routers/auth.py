from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from typing import List, Optional

from database import get_db, Employee
from schemas import Token, EmployeeCreate, EmployeeOut, EmployeeUpdate
from core import verify_password, get_password_hash, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, limiter
from routers.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Employee).where(Employee.username == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hisobingiz bloklangan. Iltimos, administratorga murojaat qiling."
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    await log_action(db, user.id, "LOGIN", f"Tizimga kirdi: @{user.username}")
    await db.commit() # Save the login log
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": user.role,
        "permissions": user.permissions,
        "username": user.username,
        "user_id": user.id
    }

@router.post("/employees", response_model=EmployeeOut)
async def create_employee(
    user: EmployeeCreate, 
    current_user: Employee = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins and managers can create employees")
    
    if current_user.role == "manager" and user.role != "cashier":
        raise HTTPException(status_code=403, detail="Menejer faqat kassir yarata oladi")
    
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
    
    await log_action(db, current_user.id, "YANGI_XODIM", f"Xodim yaratildi: {db_user.username} (Rol: {db_user.role})")
    
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.get("/employees", response_model=List[EmployeeOut])
async def get_employees(
    current_user: Employee = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "cashier"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    
    query = select(Employee)
    if current_user.role == "manager":
        query = query.where(Employee.role != "admin")
    elif current_user.role == "cashier":
        query = query.where(Employee.id == current_user.id)
        
    result = await db.execute(query)
    return result.scalars().all()
@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: int,
    user_update: EmployeeUpdate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Faqat Admin va Manager boshqa xodimlarni o'zgartira oladi.
    if current_user.role not in ["admin", "manager"] and current_user.id != employee_id:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan. Faqat admin va menejerlar xodimlarni o'zgartirishi mumkin.")
    
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    db_user = result.scalars().first()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = user_update.model_dump(exclude_unset=True)
    
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    if "is_active" in update_data and employee_id == current_user.id and update_data["is_active"] is False:
        raise HTTPException(status_code=400, detail="O'zingizni o'zingiz bloklay olmaysiz")
    
    if "is_active" in update_data and current_user.role == "manager" and db_user.role != "cashier" and db_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Menejer faqat kassirlarni bloklay oladi")

    if "role" in update_data and employee_id == current_user.id and update_data["role"] != db_user.role:
        raise HTTPException(status_code=400, detail="O'z rolingizni o'zingiz o'zgartira olmaysiz")

    if current_user.role == "manager" and db_user.role != "cashier" and db_user.id != current_user.id:
         # If a manager tries to change ANYTHING on a non-cashier who is not themselves
         raise HTTPException(status_code=403, detail="Menejer faqat kassirlarni tahrirlay oladi")

    if "role" in update_data and current_user.role == "manager" and update_data["role"] != "cashier" and db_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Menejer faqat kassir rolini bera oladi")

    # Ma'lumotlarni yangilash
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    try:
        await log_action(db, current_user.id, "XODIM_TAHRIRLANDI", f"Xodim: {db_user.username} (ID: {employee_id})")
        await db.commit()
        await db.refresh(db_user)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ma'lumotlarni saqlashda xatolik: {str(e)}")
        
    return db_user

@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: int,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete employees")
    
    if current_user.id == employee_id:
        raise HTTPException(status_code=400, detail="O'zingizni o'chira olmaysiz")
        
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    db_user = result.scalars().first()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="Employee not found")

    if db_user.username == "admin":
        raise HTTPException(status_code=400, detail="Asosiy administratorni o'chirib bo'lmaydi")
        
    await db.delete(db_user)
    
    await log_action(db, current_user.id, "XODIM_OCHIRILDI", f"Xodim o'chirildi: {db_user.username} (ID: {employee_id})")
    
    await db.commit()
    return None

@router.get("/attendance")
async def get_attendance(
    employee_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")

    from database import Attendance
    from sqlalchemy.orm import joinedload
    from datetime import datetime, timedelta

    stmt = select(Attendance).options(joinedload(Attendance.employee)).order_by(Attendance.created_at.desc())

    if employee_id:
        stmt = stmt.where(Attendance.employee_id == employee_id)
    
    if start_date:
        d = datetime.strptime(start_date, "%Y-%m-%d")
        stmt = stmt.where(Attendance.created_at >= d)
    if end_date:
        d = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        stmt = stmt.where(Attendance.created_at < d)

    result = await db.execute(stmt)
    logs = result.scalars().all()

    return logs
