"""
Database Models using SQLAlchemy
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, 
    TIMESTAMP, ForeignKey, Index, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

# pgvector support
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Component(Base):
    """
    Library components with CLIP embeddings
    """
    __tablename__ = "components"
    
    # Primary Key
    component_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Component Info
    component_name = Column(String(255), nullable=False, unique=True)
    component_type = Column(String(100))
    description = Column(Text)
    
    # Component Data (JSON)
    config_json = Column(JSONB, nullable=False)
    format_json = Column(JSONB, nullable=False)
    records_json = Column(JSONB, nullable=False)
    
    # Screenshot Info
    screenshot_url = Column(String(500))
    screenshot_path = Column(String(500))
    screenshot_hash = Column(String(64))
    
    # Visual Embedding (CLIP - 512 dimensions)
    embedding = Column(Vector(512))
    
    # Metadata
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(TIMESTAMP)
    usage_count = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Source Info
    source_component_id = Column(Integer)
    source_cms_url = Column(String(500))
    
    # Relationships
    generation_tasks = relationship("GenerationTask", back_populates="matched_component")
    
    def __repr__(self):
        return f"<Component(id={self.component_id}, name='{self.component_name}')>"


class GenerationTask(Base):
    """
    Component generation requests tracking
    """
    __tablename__ = "generation_tasks"
    
    # Primary Key
    task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Input Info
    figma_url = Column(Text, nullable=False)
    figma_file_id = Column(String(100))
    figma_node_id = Column(String(100))
    section_name = Column(String(255))
    
    # Status
    status = Column(String(50), default='pending')
    progress = Column(Integer, default=0)
    current_step = Column(String(100))
    
    # Results
    matched_component_id = Column(Integer, ForeignKey('components.component_id'))
    match_score = Column(Float)
    is_library_match = Column(Boolean, default=False)
    
    # Generated Data (if new component)
    generated_config = Column(JSONB)
    generated_format = Column(JSONB)
    generated_records = Column(JSONB)
    
    # Screenshot
    input_screenshot_path = Column(String(500))
    generated_screenshot_path = Column(String(500))
    similarity_score = Column(Float)
    
    # Agents Used
    agents_executed = Column(JSONB)
    
    # Timing
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    duration_seconds = Column(Integer)
    
    # Error Info
    error_message = Column(Text)
    error_details = Column(JSONB)
    
    # Relationships
    matched_component = relationship("Component", back_populates="generation_tasks")
    
    def __repr__(self):
        return f"<GenerationTask(id={self.task_id}, status='{self.status}')>"


class LibraryRefreshTask(Base):
    """
    Library ingestion/refresh operations tracking
    """
    __tablename__ = "library_refresh_tasks"
    
    # Primary Key
    task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Task Info
    refresh_type = Column(String(20), nullable=False)  # full, incremental
    status = Column(String(50), default='pending')
    
    # Progress Tracking
    total_components = Column(Integer, default=0)
    downloaded_components = Column(Integer, default=0)
    processed_embeddings = Column(Integer, default=0)
    stored_components = Column(Integer, default=0)
    
    # Results
    new_components_count = Column(Integer, default=0)
    updated_components_count = Column(Integer, default=0)
    failed_components_count = Column(Integer, default=0)
    
    # Current Processing
    current_component_name = Column(String(255))
    current_phase = Column(String(50))
    
    # Timing
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    duration_seconds = Column(Integer)
    estimated_time_remaining = Column(Integer)
    
    # Error Info
    error_message = Column(Text)
    failed_component_ids = Column(JSONB)
    
    # Triggered By
    triggered_by = Column(String(100))
    
    def __repr__(self):
        return f"<LibraryRefreshTask(id={self.task_id}, type='{self.refresh_type}', status='{self.status}')>"


# Create indexes
Index('idx_components_name', Component.component_name)
Index('idx_components_type', Component.component_type)
Index('idx_components_active', Component.is_active)
Index('idx_components_hash', Component.screenshot_hash)

Index('idx_generation_tasks_status', GenerationTask.status)
Index('idx_generation_tasks_created', GenerationTask.created_at)
Index('idx_generation_tasks_figma_url', GenerationTask.figma_url)

Index('idx_refresh_tasks_status', LibraryRefreshTask.status)
Index('idx_refresh_tasks_created', LibraryRefreshTask.created_at)



