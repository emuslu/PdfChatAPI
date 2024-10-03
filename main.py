import os
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.requests import Request
from dotenv import load_dotenv
from pydantic import BaseModel
import uuid
import google.generativeai as genai
from pypdf import PdfReader
import logging
from sqlalchemy import create_engine, Column, String, Text, Integer
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
import time
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from io import BytesIO

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PDF(Base):
    __tablename__ = "pdfs"

    id = Column(String, primary_key=True, index=True)
    filename = Column(String)
    content = Column(Text)
    page_count = Column(Integer)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ChatMessage(BaseModel):
    message: str

@app.post("/v1/pdf")
@limiter.limit("10/minute")
async def upload_pdf(request: Request, file: UploadFile = File(...), db: SessionLocal = Depends(get_db)):
    try:
        start_time = time.time()
        
        if not file:
            return JSONResponse(status_code=400, content={"error": "Send a PDF file!"})
        
        if not file.filename.lower().endswith('.pdf'):
            return JSONResponse(status_code=400, content={"error": "Only PDF files are allowed"})
        
        pdf_id = str(uuid.uuid4())
        
        content = await file.read()
        pdf_bytes_io = BytesIO(content)
        pdf_reader = PdfReader(pdf_bytes_io)
        text_content = ""
        for page in pdf_reader.pages:
            text_content += page.extract_text() + "\n"
        page_count = len(pdf_reader.pages)

        new_pdf = PDF(id=pdf_id, filename=file.filename, content=text_content, page_count=page_count)
        db.add(new_pdf)
        db.commit()
        
        processing_time = time.time() - start_time
        logging.info(f"PDF uploaded and processed successfully: {file.filename} (ID: {pdf_id}). Processing time: {processing_time:.2f} seconds")
        return JSONResponse(content={"pdf_id": pdf_id, "processing_time": processing_time}, status_code=201)
    
    except SQLAlchemyError as e:
        db.rollback()
        logging.error(f"Database error while uploading PDF: {str(e)}")
        raise HTTPException(status_code=500, detail="A database error occurred")
    except Exception as e:
        logging.error(f"Error uploading PDF: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the PDF")

@app.post("/v1/chat/{pdf_id}")
@limiter.limit("30/minute")
async def chat_with_pdf(request: Request, pdf_id: str, message: ChatMessage, db: SessionLocal = Depends(get_db)):
    try:
        start_time = time.time()
        
        pdf = db.query(PDF).filter(PDF.id == pdf_id).first()
        if not pdf:
            return JSONResponse(status_code=404, content={"error": "PDF not found"})
        
        prompt = f"Please answer the question according to the following PDF content:\n\n{pdf.content}\nQuestion: {message.message}\n\nAnswer:"
        
        response = model.generate_content(prompt)
        
        while response.text.endswith("...") and len(response.text) >= 8000:
            continuation_prompt = f"Continue the previous response:\n\n{response.text}"
            continuation = model.generate_content(continuation_prompt)
            response.text += continuation.text
        
        processing_time = time.time() - start_time
        logging.info(f"Chat response generated for PDF ID: {pdf_id}. Processing time: {processing_time:.2f} seconds")
        return JSONResponse(content={"response": response.text, "processing_time": processing_time})
    
    except Exception as e:
        logging.error(f"Error generating chat response: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while generating the response")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)