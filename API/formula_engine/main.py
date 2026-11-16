import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from formula_engine.api.routes import router

app = FastAPI(
    title="CerradoShift API",
    description=(
        "MVP Cerrado de apoio à decisão agrícola: clima, água, solo, "
        "sensoriamento remoto, rotação de culturas e culturas de transição."
    ),
    version="0.5.0",
)
# Libera o acesso do React durante o desenvolvimento. Em produção, defina
# CORS_ORIGINS com os domínios exatos do Front-End (sem usar *).
origins = [item.strip() for item in os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"]
)

app.include_router(router)
