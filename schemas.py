"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

class Question(BaseModel):
    """Embedded question schema for tests"""
    text: str = Field(..., description="Question text")
    type: str = Field("mcq", description="Type of question: mcq|short")
    options: Optional[List[str]] = Field(default=None, description="Options for MCQ")
    correct_index: Optional[int] = Field(default=None, description="Index of correct option for MCQ")
    answer_text: Optional[str] = Field(default=None, description="Reference answer for short questions")
    points: int = Field(1, ge=0, description="Points for this question")
    bloom_level: Optional[str] = Field(default=None, description="Bloom's taxonomy level (Remember, Understand, Apply, Analyze, Evaluate, Create)")

class Test(BaseModel):
    """
    Tests collection schema
    Collection name: "test"
    """
    title: str = Field(..., description="Test title")
    subject: Optional[str] = Field(default=None, description="Subject or topic area")
    grade_level: Optional[str] = Field(default=None, description="Grade or difficulty level")
    description: Optional[str] = Field(default=None, description="Short description")
    questions: Optional[List[Question]] = Field(default_factory=list, description="List of questions in the test")
    duration_minutes: Optional[int] = Field(default=30, ge=1, description="Suggested duration in minutes")
    tags: Optional[List[str]] = Field(default_factory=list, description="Searchable tags")

# Example schemas kept for reference but not used directly
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
