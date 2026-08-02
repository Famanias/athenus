from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_quiz_endpoint():
    response = client.get("/api/v1/learning/quizzes/med_test")
    assert response.status_code == 200
    data = response.json()
    assert "questions" in data
    assert len(data["questions"]) >= 1

def test_get_flashcards_endpoint():
    response = client.get("/api/v1/learning/flashcards/med_test")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["ease_factor"] == 2.5
