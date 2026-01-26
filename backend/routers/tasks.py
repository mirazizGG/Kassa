from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from database import get_db, Task, Employee
from schemas import TaskCreate, TaskOut, TaskUpdate
from core import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/", response_model=TaskOut)
async def create_task(
    task: TaskCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to create tasks")
    
    new_task = Task(
        title=task.title,
        description=task.description,
        status=task.status,
        assigned_to=task.assigned_to,
        created_by=current_user.id,
        due_date=task.due_date
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return new_task

@router.get("/", response_model=List[TaskOut])
async def get_tasks(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Admins/Managers see all tasks or tasks they created? Let's say all for now.
    # Employees see only their assigned tasks.
    
    query = select(Task)
    
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Task.assigned_to == current_user.id)
        
    result = await db.execute(query)
    return result.scalars().all()

@router.put("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Permission check: 
    # Admin/Manager can update anything.
    # Worker can only update status of their own task.
    
    if current_user.role not in ["admin", "manager"]:
        if task.assigned_to != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        # Workers can only update status
        if task_update.title or task_update.description or task_update.assigned_to:
             raise HTTPException(status_code=403, detail="Workers can only update status")
    
    for key, value in task_update.dict(exclude_unset=True).items():
        setattr(task, key, value)
    
    await db.commit()
    await db.refresh(task)
    return task

@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalars().first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    await db.delete(task)
    await db.commit()
    return {"message": "Task deleted"}
