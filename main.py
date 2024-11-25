from fastapi import FastAPI, Request, File, UploadFile, Form, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import SessionLocal, Client
from typing import Optional
from datetime import datetime
import pandas as pd
import shutil
import os
from pathlib import Path
from referral import create_referral
from database import SessionLocal, Client

app = FastAPI()

# Создаем необходимые директории, если они не существуют
STATIC_DIR = Path("static")
PHOTOS_DIR = STATIC_DIR / "photos"
RESULTS_DIR = STATIC_DIR / "results"
EXPORTS_DIR = STATIC_DIR / "exports"

for dir_path in [STATIC_DIR, PHOTOS_DIR, RESULTS_DIR, EXPORTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_upload_file(upload_file: UploadFile, destination: Path) -> str:
    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return str(destination.relative_to(STATIC_DIR))
    finally:
        upload_file.file.close()


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("registration.html", {"request": request})


@app.get("/registration")
async def registration_page(request: Request):
    return templates.TemplateResponse("registration.html", {"request": request})


@app.post("/registration")
async def create_client(
        request: Request,
        db: Session = Depends(get_db),
        name: str = Form(...),
        user_photo: UploadFile = File(...),
        date_of_birth: str = Form(...),
        user_passport_id: str = Form(...),
        passport_photo: UploadFile = File(...),
        user_phone_number: str = Form(...),
        migrating_country: str = Form(...)
):
    try:
        # Проверяем существование клиента с таким паспортом
        existing_client = db.query(Client).filter(Client.user_passport_id == user_passport_id).first()
        if existing_client:
            return templates.TemplateResponse(
                "registration.html",
                {
                    "request": request,
                    "error": "Клиент с таким номером паспорта уже существует"
                },
                status_code=400
            )

        # Сохраняем файлы
        user_photo_path = PHOTOS_DIR / f"{user_passport_id}_user{Path(user_photo.filename).suffix}"
        passport_photo_path = PHOTOS_DIR / f"{user_passport_id}_passport{Path(passport_photo.filename).suffix}"

        user_photo_rel_path = save_upload_file(user_photo, user_photo_path)
        passport_photo_rel_path = save_upload_file(passport_photo, passport_photo_path)

        # Создаем запись в БД
        client = Client(
            name=name,
            user_photo=user_photo_rel_path,
            date_of_birth=datetime.strptime(date_of_birth, "%Y-%m-%d").date(),
            user_passport_id=user_passport_id,
            passport_photo=passport_photo_rel_path,
            user_phone_number=user_phone_number,
            migrating_country=migrating_country
        )

        db.add(client)
        db.commit()
        db.refresh(client)

        return templates.TemplateResponse(
            "registration.html",
            {
                "request": request,
                "success": "Клиент успешно зарегистрирован"
            }
        )

    except Exception as e:
        # Если произошла ошибка, удаляем загруженные файлы
        for path in [user_photo_path, passport_photo_path]:
            if path.exists():
                path.unlink()

        return templates.TemplateResponse(
            "registration.html",
            {
                "request": request,
                "error": f"Ошибка при регистрации: {str(e)}"
            },
            status_code=500
        )


@app.post("/upload_result/{user_id}")
async def upload_result(
        user_id: int,
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    client = db.query(Client).filter(Client.user_id == user_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    try:
        # Сохраняем файл результата
        result_path = RESULTS_DIR / f"{user_id}_{file.filename}"
        result_rel_path = save_upload_file(file, result_path)

        client.final_result = result_rel_path
        db.commit()

        return {"status": "success", "file_path": result_rel_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке файла: {str(e)}")


@app.get("/download_excel/{page}")
async def download_excel(page: str, db: Session = Depends(get_db)):
    try:
        if page == "clinic":
            clients = db.query(Client).filter(Client.status == False).all()
        elif page == "assess":
            clients = db.query(Client).filter(Client.assess == True).all()
        else:
            clients = db.query(Client).all()

        # Создание DataFrame для Excel
        data = []
        for client in clients:
            data.append({
                "ID": client.user_id,
                "Имя": client.name,
                "Дата рождения": client.date_of_birth.strftime("%d.%m.%Y"),
                "Паспорт": client.user_passport_id,
                "Телефон": client.user_phone_number,
                "Страна": client.migrating_country,
                "Дата регистрации": client.reg_date.strftime("%d.%m.%Y"),
                "Статус": "Прошел" if client.status else "Не прошел",
                "Оценка": "Годен" if client.assess else "Не годен"
            })

        df = pd.DataFrame(data)
        excel_path = EXPORTS_DIR / f"{page}_clients.xlsx"
        df.to_excel(excel_path, index=False)

        return FileResponse(
            str(excel_path),
            filename=f"{page}_clients.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании Excel файла: {str(e)}")


# Добавляем остальные эндпойнты...
@app.get("/registration2")
async def registration2_page(request: Request):
    return templates.TemplateResponse("registration2.html", {"request": request})


@app.get("/clinic_client")
async def clinic_client_page(request: Request, db: Session = Depends(get_db)):
    clients = db.query(Client).filter(Client.status == False).all()
    return templates.TemplateResponse("clinic_client.html", {
        "request": request,
        "clients": clients
    })


@app.get("/assess_clients")
async def assess_clients_page(request: Request, db: Session = Depends(get_db)):
    clients = db.query(Client).filter(Client.assess == True).all()
    return templates.TemplateResponse("assess_clients.html", {
        "request": request,
        "clients": clients
    })


@app.get("/all_clients")
async def all_clients_page(request: Request, db: Session = Depends(get_db)):
    clients = db.query(Client).all()
    return templates.TemplateResponse("all_clients.html", {
        "request": request,
        "clients": clients
    })


@app.put("/update_status/{user_id}")
async def update_status(
        user_id: int,
        db: Session = Depends(get_db)
):
    try:
        client = db.query(Client).filter(Client.user_id == user_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Клиент не найден")

        client.status = not client.status
        db.commit()

        return JSONResponse(content={"success": True, "status": client.status})
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/update_assess/{user_id}")
async def update_assess(
        user_id: int,
        db: Session = Depends(get_db)
):
    try:
        client = db.query(Client).filter(Client.user_id == user_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Клиент не найден")

        client.assess = not client.assess
        db.commit()

        return JSONResponse(content={"success": True, "assess": client.assess})
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/registration")
async def create_client(
        request: Request,
        db: Session = Depends(get_db),
        name: str = Form(...),
        user_photo: UploadFile = File(...),
        date_of_birth: str = Form(...),
        user_passport_id: str = Form(...),
        passport_photo: UploadFile = File(...),
        user_phone_number: str = Form(...),
        migrating_country: str = Form(...)
):
    try:
        # Создание директорий, если они не существуют
        os.makedirs("static/photos", exist_ok=True)
        os.makedirs("referrals", exist_ok=True)

        # Сохранение файлов
        user_photo_path = f"static/photos/{user_passport_id}_user.jpg"
        passport_photo_path = f"static/photos/{user_passport_id}_passport.jpg"

        with open(user_photo_path, "wb") as buffer:
            shutil.copyfileobj(user_photo.file, buffer)
        with open(passport_photo_path, "wb") as buffer:
            shutil.copyfileobj(passport_photo.file, buffer)

        # Создание записи в БД
        client = Client(
            name=name,
            user_photo=user_photo_path,
            date_of_birth=datetime.strptime(date_of_birth, "%Y-%m-%d").date(),
            user_passport_id=user_passport_id,
            passport_photo=passport_photo_path,
            user_phone_number=user_phone_number,
            migrating_country=migrating_country,
            reg_date=datetime.now(),
            status=False,
            assess=False
        )

        db.add(client)
        db.commit()
        db.refresh(client)

        # Генерация направления
        pdf_path = create_referral(client)
        client.referral_for_tests = pdf_path
        db.commit()

        # Перенаправляем на страницу загрузки с параметром success
        return RedirectResponse(
            url=f"/registration_success?user_id={client.user_id}&download=true",
            status_code=303
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/registration_success")
async def registration_success(
        request: Request,
        user_id: int,
        download: bool = False,
        db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        "registration_success.html",
        {
            "request": request,
            "user_id": user_id,
            "download": download
        }
    )


@app.get("/download_referral/{user_id}")
async def download_referral(user_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.user_id == user_id).first()
    if not client or not client.referral_for_tests:
        raise HTTPException(status_code=404, detail="Referral not found")

    return FileResponse(
        client.referral_for_tests,
        filename=f"referral_{client.user_passport_id}.pdf",
        media_type="application/pdf"
    )



# Добавляем в main.py новые эндпоинты:
@app.post("/generate_referral/{user_id}")
async def generate_referral(user_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.user_id == user_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Создаем направление
    pdf_path = create_referral(client)

    # Обновляем путь к направлению в базе данных
    client.referral_for_tests = pdf_path
    db.commit()

    return {"message": "Referral generated successfully", "path": pdf_path}

