import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    config_path: Mapped[str] = mapped_column(String, nullable=True)

    documents: Mapped[list["Document"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    concept_nodes: Mapped[list["ConceptNode"]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[str] = mapped_column(String, ForeignKey("subjects.subject_id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    document_type: Mapped[str] = mapped_column(String, nullable=False)  # pdf, csv, txt
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subject: Mapped["Subject"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")  # JSON string

    document: Mapped["Document"] = relationship(back_populates="chunks")


class QuizItem(Base):
    __tablename__ = "quiz_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    subject_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    explanation: Mapped[str] = mapped_column(Text, default="")
    quiz_type: Mapped[str] = mapped_column(String, default="multiple_choice")
    difficulty: Mapped[str] = mapped_column(String, default="medium")
    concept_tags_json: Mapped[str] = mapped_column(Text, default="[]")
    source_chunk_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    output_language: Mapped[str] = mapped_column(String, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    attempts: Mapped[list["QuizAttempt"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(String, ForeignKey("quiz_items.id"), nullable=False, index=True)
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    item: Mapped["QuizItem"] = relationship(back_populates="attempts")


class ConceptNode(Base):
    __tablename__ = "concept_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[str] = mapped_column(String, ForeignKey("subjects.subject_id"), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String, nullable=False)  # Topic, Concept, Definition, etc.
    label: Mapped[str] = mapped_column(String, nullable=False)

    subject: Mapped["Subject"] = relationship(back_populates="concept_nodes")
    outgoing_edges: Mapped[list["ConceptEdge"]] = relationship(
        foreign_keys="ConceptEdge.source_id", back_populates="source", cascade="all, delete-orphan"
    )
    incoming_edges: Mapped[list["ConceptEdge"]] = relationship(
        foreign_keys="ConceptEdge.target_id", back_populates="target", cascade="all, delete-orphan"
    )


class ConceptEdge(Base):
    __tablename__ = "concept_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("concept_nodes.id"), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, ForeignKey("concept_nodes.id"), nullable=False)
    edge_type: Mapped[str] = mapped_column(String, nullable=False)  # CONTAINS, MENTIONS, DEFINES, etc.

    source: Mapped["ConceptNode"] = relationship(foreign_keys=[source_id], back_populates="outgoing_edges")
    target: Mapped["ConceptNode"] = relationship(foreign_keys=[target_id], back_populates="incoming_edges")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    subject_id: Mapped[str] = mapped_column(String, ForeignKey("subjects.subject_id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subject: Mapped["Subject"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_chunk_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
