from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from database import get_db, Client, Employee
from schemas import ClientCreate, ClientOut
from core import get_current_user

router = APIRouter(prefix="/crm", tags=["crm"])

@router.get("/clients", response_model=List[ClientOut])
async def get_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client))
    return result.scalars().all()

@router.post("/clients", response_model=ClientOut)
async def create_client(
    client: ClientCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db_client = Client(**client.model_dump())
    db.add(db_client)
    await db.commit()
    await db.refresh(db_client)
    return db_client

@router.get("/clients/{client_id}", response_model=ClientOut)
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
