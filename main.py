import os
import random
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Utilities ---------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def serialize_doc(doc: dict):
    if not doc:
        return doc
    doc = dict(doc)
    if doc.get("_id") is not None:
        doc["id"] = str(doc.pop("_id"))
    # Convert datetimes to isoformat if present
    for k in ("created_at", "updated_at"):
        if k in doc and hasattr(doc[k], "isoformat"):
            doc[k] = doc[k].isoformat()
    return doc


# --------- Models ---------
class Question(BaseModel):
    text: str
    type: str = Field("mcq", description="mcq|short")
    options: Optional[List[str]] = None
    correct_index: Optional[int] = None
    answer_text: Optional[str] = None
    points: int = 1
    bloom_level: Optional[str] = None


class TestModel(BaseModel):
    title: str
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    description: Optional[str] = None
    questions: List[Question] = Field(default_factory=list)
    duration_minutes: Optional[int] = 30
    tags: List[str] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    topic: str = Field(..., description="Topic to generate questions about")
    grade_level: Optional[str] = Field(default=None)
    num_questions: int = Field(5, ge=1, le=50)
    question_type: str = Field("mcq", description="mcq|short|mixed")


# --------- Simple AI-ish generator ---------
BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create",
]


def generate_mcq(topic: str, grade: Optional[str], idx: int) -> Question:
    verbs = {
        "Remember": ["define", "list", "identify", "recall"],
        "Understand": ["explain", "describe", "summarize", "classify"],
        "Apply": ["use", "demonstrate", "solve", "compute"],
        "Analyze": ["compare", "distinguish", "analyze", "differentiate"],
        "Evaluate": ["assess", "justify", "critique", "evaluate"],
        "Create": ["design", "compose", "develop", "formulate"],
    }
    bloom = random.choice(BLOOM_LEVELS)
    verb = random.choice(verbs[bloom])
    stem = f"Q{idx+1}. In the context of {topic}, {verb} the correct option." if bloom in ["Apply", "Analyze", "Evaluate", "Create"] else f"Q{idx+1}. Which of the following best relates to {topic}?"

    # Create 4 options with one correct
    correct = None
    if bloom in ["Remember", "Understand"]:
        correct = f"A concise fact about {topic}"
        distractors = [
            f"An unrelated idea about {topic}",
            f"A partially correct idea about {topic}",
            f"A common misconception about {topic}",
        ]
    else:
        correct = f"An example that shows how to {verb} using {topic}"
        distractors = [
            f"An example unrelated to {topic}",
            f"Incorrect application of {topic}",
            f"Vague statement without using {topic}",
        ]

    options = distractors + [correct]
    random.shuffle(options)
    correct_index = options.index(correct)

    return Question(
        text=stem,
        type="mcq",
        options=options,
        correct_index=correct_index,
        points=1,
        bloom_level=bloom,
    )


def generate_short(topic: str, grade: Optional[str], idx: int) -> Question:
    bloom = random.choice(BLOOM_LEVELS)
    stem = f"Q{idx+1}. Briefly explain the following about {topic}:"
    return Question(
        text=stem,
        type="short",
        answer_text=f"A 2-3 sentence explanation referencing {topic}.",
        points=2,
        bloom_level=bloom,
    )


def generate_questions(req: GenerateRequest) -> List[Question]:
    qs: List[Question] = []
    for i in range(req.num_questions):
        qtype = req.question_type
        if qtype == "mixed":
            qtype = random.choice(["mcq", "short"])  # mix
        if qtype == "short":
            qs.append(generate_short(req.topic, req.grade_level, i))
        else:
            qs.append(generate_mcq(req.topic, req.grade_level, i))
    return qs


# --------- Routes ---------
@app.get("/")
def read_root():
    return {"message": "AI Test Maker Backend Ready"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    # Check env
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


@app.post("/api/tests/generate")
def generate_test(req: GenerateRequest):
    title = f"{req.topic.title()} - {req.num_questions} Question Test"
    questions = generate_questions(req)
    payload = TestModel(
        title=title,
        subject=req.topic,
        grade_level=req.grade_level,
        description=f"Auto-generated {req.question_type} test about {req.topic}",
        questions=questions,
        duration_minutes=max(10, req.num_questions * 2),
        tags=["auto", "generated", req.topic],
    )
    return payload.model_dump()


@app.post("/api/tests")
def save_test(test: TestModel):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    test_dict = test.model_dump()
    inserted_id = create_document("test", test_dict)
    return {"id": inserted_id}


@app.get("/api/tests")
def list_tests(limit: int = 25):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    docs = get_documents("test", limit=limit)
    return [serialize_doc(d) for d in docs]


@app.get("/api/tests/{test_id}")
def get_test(test_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    if not ObjectId.is_valid(test_id):
        raise HTTPException(status_code=400, detail="Invalid id")
    doc = db["test"].find_one({"_id": ObjectId(test_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_doc(doc)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
