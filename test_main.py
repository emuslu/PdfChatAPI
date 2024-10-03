import pytest
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app, Base, get_db
import io
from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_DATABASE_URL = "sqlite:///./ut.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture
def test_pdf():


    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 100, "This is a test PDF file.")
    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer

def test_upload_pdf(test_pdf):
    response = client.post(
        "/v1/pdf",
        files={"file": ("test.pdf", test_pdf, "application/pdf")},
    )
    assert response.status_code == 201
    assert "pdf_id" in response.json()
    assert "processing_time" in response.json()

def test_upload_invalid_file():
    response = client.post(
        "/v1/pdf",
        files={"file": ("test.txt", io.BytesIO(b"Hello"), "text/plain")},
    )
    assert response.status_code == 400
    assert {'error': 'Only PDF files are allowed'} == response.json()

def test_chat_with_pdf(test_pdf):
    upload_response = client.post(
        "/v1/pdf",
        files={"file": ("test.pdf", test_pdf, "application/pdf")},
    )
    pdf_id = upload_response.json()["pdf_id"]

    chat_response = client.post(
        f"/v1/chat/{pdf_id}",
        json={"message": "What is the content of the PDF?"},
    )
    assert chat_response.status_code == 200
    assert "response" in chat_response.json()
    assert "processing_time" in chat_response.json()

def test_chat_with_nonexistent_pdf():
    response = client.post(
        "/v1/chat/nonexistent_id",
        json={"message": "This should fail"},
    )
    assert response.status_code == 404
    assert {"error": "PDF not found"} == response.json()

if __name__ == "__main__":
    pytest.main([__file__])